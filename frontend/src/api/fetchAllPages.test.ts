import test from "node:test";
import assert from "node:assert/strict";
import type { PaginationParams } from "../types/common";
import { fetchAllPages } from "./fetchAllPages.js";
import { normalizeListResponse } from "./normalizeListResponse.js";

function paginatedApi<T>(records: T[], cap = 100) {
  const requests: PaginationParams[] = [];
  return {
    requests,
    async list(params: PaginationParams = {}) {
      requests.push(params);
      const page = params.page || 1;
      const limit = Math.min(params.limit || 20, cap);
      return {
        items: records.slice((page - 1) * limit, page * limit),
        total: records.length,
        page,
        page_size: limit,
      };
    },
  };
}

test("all 20 companies retain their 10 filiales and 5 sites beyond the first page", async () => {
  const branches = Array.from({ length: 200 }, (_, index) => ({
    id: index + 1,
    company_id: Math.floor(index / 10) + 1,
  }));
  const sites = branches.flatMap((branch) =>
    Array.from({ length: 5 }, (_, index) => ({
      id: (branch.id - 1) * 5 + index + 1,
      company_id: branch.company_id,
      branch_id: branch.id,
    })),
  );
  const branchApi = paginatedApi(branches);
  const siteApi = paginatedApi(sites);
  const [loadedBranches, loadedSites] = await Promise.all([
    fetchAllPages(branchApi), fetchAllPages(siteApi),
  ]);
  assert.deepEqual(loadedBranches.items, branches);
  assert.deepEqual(loadedSites.items, sites);
  assert.equal(branchApi.requests.length, 2);
  assert.equal(siteApi.requests.length, 10);
  for (let companyId = 1; companyId <= 20; companyId += 1) {
    const options = loadedBranches.items.filter((branch) => branch.company_id === companyId);
    assert.equal(options.length, 10);
    for (const branch of options) {
      assert.equal(loadedSites.items.filter((site) =>
        site.company_id === companyId && site.branch_id === branch.id).length, 5);
    }
  }
  assert.deepEqual(siteApi.requests[0], { page: 1, limit: 100, sort_by: "id", sort_order: "asc" });
});

test("supports empty lists, partial final pages, and smaller server page limits", async () => {
  for (const length of [0, 21, 205, 1101]) {
    const records = Array.from({ length }, (_, id) => ({ id }));
    const api = paginatedApi(records, 20);
    assert.deepEqual((await fetchAllPages(api)).items, records);
    assert.equal(api.requests.length, Math.max(1, Math.ceil(length / 20)));
  }
});

test("failed later pages reject instead of displaying incomplete options", async () => {
  const api = paginatedApi(Array.from({ length: 200 }, (_, id) => ({ id })));
  const list = api.list;
  api.list = async (params) => {
    if (params?.page === 2) throw new Error("Network unavailable");
    return list(params);
  };
  await assert.rejects(fetchAllPages(api), /Network unavailable/);
});

test("an empty page before the reported total fails without looping", async () => {
  await assert.rejects(fetchAllPages({
    list: async () => ({ items: [], total: 200, page: 1, page_size: 100 }),
  }), /could not be fully loaded/);
});

test("medical tests load every active result using backend meta pagination", async () => {
  const records = Array.from({ length: 237 }, (_, id) => ({ id, active: id % 3 !== 0 }));
  const activeTests = records.filter((item) => item.active);
  const requests: Array<PaginationParams & { active: boolean }> = [];
  const medicalApi = {
    async list(params: PaginationParams & { active: boolean }) {
      requests.push(params);
      const filtered = params.active ? activeTests : records;
      const page = params.page || 1;
      const limit = params.limit || 20;
      return normalizeListResponse({
        items: filtered.slice((page - 1) * limit, page * limit),
        meta: { page, limit, total: filtered.length, pages: Math.ceil(filtered.length / limit) },
      }, params);
    },
  };
  const result = await fetchAllPages({
    list: (params) => medicalApi.list({ ...params, active: true }),
  });
  assert.deepEqual(result.items, activeTests);
  assert.equal(requests.length, 2);
  assert.ok(requests.every((request) => request.active === true && request.limit === 100));
});

test("list normalization preserves empty metadata and supports legacy response shapes", () => {
  assert.deepEqual(normalizeListResponse({
    items: [], meta: { total: 0, page: 1, limit: 100, pages: 1 },
  }), { items: [], total: 0, page: 1, page_size: 100 });
  const flat = { items: [{ id: 1 }], total: 51, page: 2, page_size: 50 };
  assert.deepEqual(normalizeListResponse(flat), flat);
  assert.deepEqual(normalizeListResponse([{ id: 1 }]), {
    items: [{ id: 1 }], total: 1, page: 1, page_size: 1,
  });
});
