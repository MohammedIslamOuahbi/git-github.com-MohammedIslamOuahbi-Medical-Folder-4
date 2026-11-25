const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const axios = require('axios');

const root = path.resolve(__dirname, '..');
const read = (file) => new TextDecoder('utf-8', { fatal: true }).decode(fs.readFileSync(path.join(root, file)));
const safetyModule = { exports: {} };
vm.runInNewContext(ts.transpileModule(read('src/services/syncSafety.ts'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports: safetyModule.exports });
const safety = safetyModule.exports;
const source = read('src/pages/companies/CompaniesPage.tsx');
const tree = ts.createSourceFile('CompaniesPage.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const handlers = {};
function visit(node) {
  if (ts.isVariableDeclaration(node) && ['save', 'saveBranch', 'saveSite'].includes(node.name.getText(tree))) {
    handlers[node.name.getText(tree)] = node.initializer.getText(tree);
  }
  ts.forEachChild(node, visit);
}
visit(tree);

function httpError(status, data) {
  return new axios.AxiosError('Request failed', undefined, {}, undefined, { status, data });
}
const suspended = httpError(423, { success: false, details: { code: safety.SYNC_SAFETY_CODE } });
const suspensionMessage = 'Création temporairement suspendue pour la sécurité des données.';
const cases = [
  ['structured suspension', suspended, suspensionMessage],
  ['desktop suspension', safety.suspendedSyncError(), suspensionMessage],
  ['forbidden', httpError(403, {}), 'Vous n’avez pas les droits nécessaires pour cette opération.'],
  ['unrelated lock', httpError(423, { details: { code: 'OTHER_LOCK' } }), null],
  ['validation', httpError(422, { message: 'Validation error' }), null],
  ['server failure', httpError(500, {}), null],
  ['network failure', new axios.AxiosError('Network Error', 'ERR_NETWORK'), null],
];

for (const [handler, setter, entity] of [
  ['save', 'setSaveError', 'l’entreprise'],
  ['saveBranch', 'setBranchSaveError', 'la filiale'],
  ['saveSite', 'setSiteSaveError', 'le site'],
]) {
  for (const [label, error, expected] of cases) {
    test(`${handler}: ${label} preserves form and reports the correct error`, async () => {
      const messages = [];
      const forbiddenChanges = [];
      let requests = 0;
      const form = Object.freeze({ name: 'Unsaved input', company_id: 1, branch_id: 2 });
      const api = { create: async () => { requests++; throw error; } };
      const context = {
        axios, isSafetySuspension: safety.isSafetySuspension,
        validateForm: () => true, generateCompanyCode: () => 'UNSAVED',
        form, branchForm: form, siteForm: form, branchDrafts: [],
        editingId: null, editingBranchId: null, editingSiteId: null,
        companiesApi: api, branchesApi: api, drillingSitesApi: api,
        normalizeCompany: (value) => value,
        defaultBranchForm: {}, defaultSiteForm: {},
      };
      for (const name of ['setSaveError', 'setBranchSaveError', 'setSiteSaveError', 'resetEditor',
        'setItems', 'setAllBranches', 'setAllSites', 'setBranchModalOpen', 'setSiteModalOpen',
        'setBranchForm', 'setSiteForm', 'setEditingBranchId', 'setEditingSiteId']) {
        context[name] = name === setter ? (value) => messages.push(value) : () => forbiddenChanges.push(name);
      }
      const executable = ts.transpileModule(`(${handlers[handler]})`, {
        compilerOptions: { target: ts.ScriptTarget.ES2022 },
      }).outputText;
      await vm.runInNewContext(executable, context)();
      assert.equal(requests, 1);
      const expectedMessage = handler === 'save' && label === 'validation'
        ? 'Les données saisies sont invalides. Vérifiez les champs du formulaire.'
        : expected || `Impossible d’enregistrer ${entity}.`;
      assert.deepEqual(messages, [null, expectedMessage]);
      assert.deepEqual(forbiddenChanges, []);
      assert.equal(form.name, 'Unsaved input');
    });
  }
}

test('API interceptor preserves the original suspension status and structured response', async () => {
  let rejectResponse;
  const client = { interceptors: {
    request: { use() {} },
    response: { use(_success, failure) { rejectResponse = failure; } },
  } };
  const compiled = ts.transpileModule(read('src/api/axios.ts'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(compiled, {
    exports: {},
    require(name) {
      if (name === 'axios') return { create: () => client };
      if (name.includes('syncSafety')) return safety;
      if (name === '@/config/env') return { env: { apiBaseUrl: 'http://localhost' } };
      if (name === '@/config/runtime' || name === '@/utils/storage') return {};
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  await assert.rejects(rejectResponse(suspended), (error) => {
    assert.equal(error, suspended);
    assert.equal(error.response.status, 423);
    assert.equal(error.response.data.details.code, safety.SYNC_SAFETY_CODE);
    return true;
  });
});

test('each modal renders its own error and corrupted French literals are absent', () => {
  for (const state of ['saveError', 'branchSaveError', 'siteSaveError']) {
    assert.ok(source.includes(`{${state} ? (`));
    assert.ok(source.includes(`{${state}}`));
  }
  assert.doesNotMatch(source, /d\?enregistrer|l\?entreprise|n\?avez|n\?cessaires|op\?ration|Cr\?ation/);
});

function loadCompanyApi(baseURL = 'http://localhost') {
  const cache = new Map();
  function load(file) {
    if (cache.has(file)) return cache.get(file);
    const exports = {};
    cache.set(file, exports);
    const code = ts.transpileModule(read(file), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    vm.runInNewContext(code, {
      exports,
      require(name) {
        if (name === 'axios') return axios;
        if (name === '@/config/env') return { env: { apiBaseUrl: baseURL } };
        if (name === '@/config/runtime') return {};
        if (name === '@/utils/storage') return {
          tokenStorage: { getAccessToken: () => null },
          missionStorage: { getCredential: () => null, getCachedDevice: () => null },
        };
        return load(path.posix.normalize(path.posix.join(path.posix.dirname(file), `${name}.ts`)));
      },
    });
    return exports;
  }
  return { companiesApi: load('src/api/companiesApi.ts').companiesApi, client: load('src/api/axios.ts').default };
}

test('company API normalizes optional email without mutating inputs or clearing omitted updates', async () => {
  const { companiesApi, client } = loadCompanyApi();
  const payloads = [];
  client.defaults.adapter = async (config) => {
    payloads.push(JSON.parse(config.data));
    return { status: 200, data: {}, config, headers: {}, statusText: 'OK' };
  };
  for (const email of ['', '   ', null, undefined, ' synthetic@example.com ']) {
    const input = Object.freeze({ name: 'Synthetic input', email });
    await companiesApi.create(input);
    await companiesApi.update(1, input);
    for (const sent of payloads.slice(-2)) {
      if (email === undefined) assert.equal('email' in sent, false);
      else assert.equal(sent.email, email?.trim() || null);
    }
    assert.equal(input.email, email);
  }
});

test('email validation response marks the field without closing or clearing the form', async () => {
  const messages = [];
  let fieldErrors = {};
  const execute = ts.transpileModule(`(${handlers.save})`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  await vm.runInNewContext(execute, {
    axios, isSafetySuspension: safety.isSafetySuspension,
    validateForm: () => true, generateCompanyCode: () => 'CMP-SYNTHETIC',
    form: Object.freeze({ name: 'Synthetic', email: 'invalid' }), branchDrafts: [], editingId: null,
    normalizeCompany: (value) => value,
    companiesApi: { create: async () => { throw httpError(422, {
      details: { errors: [{ loc: ['body', 'email'], type: 'value_error' }] },
    }); } },
    setSaveError: (value) => messages.push(value),
    setFormErrors: (update) => { fieldErrors = update(fieldErrors); },
  })();
  assert.equal(fieldErrors.email, 'Saisissez une adresse e-mail valide.');
  assert.equal(messages.at(-1), 'Les données saisies sont invalides. Vérifiez les champs du formulaire.');
});

test('real HTTP: blank email returns 422; company API normalization reaches the unchanged 423 barrier', {
  skip: !process.env.COMPANY_DIAGNOSTIC_URL,
}, async () => {
  const baseURL = process.env.COMPANY_DIAGNOSTIC_URL;
  const input = Object.freeze({
    name: 'Synthetic company HTTP diagnostic', email: '', code: 'CMP-DIAGNOSTIC',
    contract_start_date: '2026-10-01', contract_end_date: '2027-10-01',
  });
  await assert.rejects(axios.post(`${baseURL}/companies`, input), (error) => {
    assert.equal(error.response.status, 422);
    assert.deepEqual(error.response.data.details.errors[0].loc, ['body', 'email']);
    console.log('Before normalization:', JSON.stringify({ status: error.response.status, body: error.response.data }));
    return true;
  });
  const { companiesApi } = loadCompanyApi(baseURL);
  const messages = [];
  const execute = ts.transpileModule(`(${handlers.save})`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  await vm.runInNewContext(execute, {
    axios, isSafetySuspension: safety.isSafetySuspension,
    validateForm: () => true, generateCompanyCode: () => 'CMP-DIAGNOSTIC',
    form: input, branchDrafts: [], editingId: null, normalizeCompany: (value) => value,
    companiesApi: { create: async (payload) => {
      try { return await companiesApi.create(payload); }
      catch (error) {
        assert.equal(error.response.status, 423);
        assert.equal(error.response.data.details.code, safety.SYNC_SAFETY_CODE);
        console.log('After normalization:', JSON.stringify({ status: error.response.status, body: error.response.data }));
        throw error;
      }
    } },
    setSaveError: (value) => messages.push(value),
  })();
  assert.deepEqual(messages, [null, suspensionMessage]);
  assert.equal(input.email, '');
});
