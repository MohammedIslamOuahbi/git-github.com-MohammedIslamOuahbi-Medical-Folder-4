import test from "node:test";
import assert from "node:assert/strict";
import { runtimeConnectionService, shouldRequireDatabaseHealth } from "./runtimeConnectionService.js";
class MemoryStorage {
    store = new Map();
    get length() {
        return this.store.size;
    }
    clear() {
        this.store.clear();
    }
    getItem(key) {
        return this.store.has(key) ? this.store.get(key) : null;
    }
    key(index) {
        return Array.from(this.store.keys())[index] ?? null;
    }
    removeItem(key) {
        this.store.delete(key);
    }
    setItem(key, value) {
        this.store.set(key, value);
    }
}
const originalWindow = globalThis.window;
const originalFetch = globalThis.fetch;
const createJsonResponse = (body, init) => new Response(JSON.stringify(body), {
    status: 200,
    headers: {
        "Content-Type": "application/json",
    },
    ...init,
});
test.beforeEach(() => {
    const localStorage = new MemoryStorage();
    const sessionStorage = new MemoryStorage();
    globalThis.window = {
        setTimeout: globalThis.setTimeout.bind(globalThis),
        clearTimeout: globalThis.clearTimeout.bind(globalThis),
        localStorage,
        sessionStorage,
    };
});
test.afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
});
test("database health remains required for server mode only", () => {
    assert.equal(shouldRequireDatabaseHealth("server"), true);
    assert.equal(shouldRequireDatabaseHealth("client"), false);
});
test("client validation succeeds when health is ok and database endpoint is unavailable", async () => {
    globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.endsWith("/health")) {
            return createJsonResponse({ status: "ok" });
        }
        if (url.endsWith("/health/identity")) {
            return createJsonResponse({
                application: "medical-folder",
            });
        }
        if (url.endsWith("/health/database")) {
            return new Response(JSON.stringify({ detail: "missing" }), { status: 404 });
        }
        throw new Error(`Unexpected URL: ${url}`);
    };
    const result = await runtimeConnectionService.validateConnection({
        mode: "client",
        rawUrl: "http://192.168.1.50:8000",
        persist: false,
    });
    assert.equal(result.success, true);
    assert.equal(result.healthOk, true);
    assert.equal(result.databaseOk, true);
    assert.equal(result.apiBaseUrl, "http://192.168.1.50:8000/api/v1");
});
test("server validation still fails when database endpoint is unavailable", async () => {
    globalThis.fetch = async (input) => {
        const url = String(input);
        if (url.endsWith("/health")) {
            return createJsonResponse({ status: "ok" });
        }
        if (url.endsWith("/health/database")) {
            return new Response(JSON.stringify({ detail: "missing" }), { status: 404 });
        }
        throw new Error(`Unexpected URL: ${url}`);
    };
    const result = await runtimeConnectionService.validateConnection({
        mode: "server",
        rawUrl: "http://127.0.0.1:8000",
        persist: false,
    });
    assert.equal(result.success, false);
    assert.equal(result.errorCode, "DATABASE_HEALTH_UNAVAILABLE");
    assert.equal(result.healthOk, true);
    assert.equal(result.databaseOk, false);
});
