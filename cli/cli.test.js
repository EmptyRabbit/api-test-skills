"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { describe, it, beforeEach, afterEach } = require("node:test");

const { main } = require("./lib");

function mkdirs() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "api-test-skills-cli-"));
  const homedir = path.join(root, "home");
  const cwd = path.join(root, "proj");
  fs.mkdirSync(homedir);
  fs.mkdirSync(cwd);
  return { root, homedir, cwd };
}

function userFile(dirs) {
  return path.join(dirs.homedir, ".api-test-skills.yaml");
}

function projectFile(dirs) {
  return path.join(dirs.cwd, ".api-test-skills.yaml");
}

async function run(argv, dirs) {
  return main(argv, { cwd: dirs.cwd, homedir: dirs.homedir });
}

describe("api-test-skills CLI", () => {
  let dirs;

  beforeEach(() => {
    dirs = mkdirs();
  });

  afterEach(() => {
    fs.rmSync(dirs.root, { recursive: true, force: true });
  });

  it("use <vendor> writes ~/.api-test-skills.yaml", async () => {
    const result = await run(["use", "example"], dirs);
    assert.equal(result.code, 0);
    assert.equal(
      fs.readFileSync(userFile(dirs), "utf8"),
      "vendor: example\n"
    );
    assert.equal(fs.existsSync(projectFile(dirs)), false);
  });

  it("use <vendor> --project writes ./.api-test-skills.yaml", async () => {
    const result = await run(["use", "example", "--project"], dirs);
    assert.equal(result.code, 0);
    assert.equal(
      fs.readFileSync(projectFile(dirs), "utf8"),
      "vendor: example\n"
    );
    assert.equal(fs.existsSync(userFile(dirs)), false);
  });

  it("use none writes vendor: none to the user config", async () => {
    const result = await run(["use", "none"], dirs);
    assert.equal(result.code, 0);
    assert.equal(fs.readFileSync(userFile(dirs), "utf8"), "vendor: none\n");
  });

  it("status reports none when no config exists", async () => {
    const result = await run(["status"], dirs);
    assert.equal(result.code, 0);
    assert.match(result.stdout, /vendor:\s*none/);
    assert.match(result.stdout, /source:\s*未配置/);
  });

  it("status prefers project config over user config", async () => {
    fs.writeFileSync(userFile(dirs), "vendor: user-vendor\n");
    fs.writeFileSync(projectFile(dirs), "vendor: proj-vendor\n");
    const result = await run(["status"], dirs);
    assert.equal(result.code, 0);
    assert.match(result.stdout, /vendor:\s*proj-vendor/);
    assert.match(result.stdout, /source:\s*project/);
    assert.match(result.stdout, /api-test-skills\.yaml/);
  });

  it("status falls back to user config", async () => {
    fs.writeFileSync(userFile(dirs), "vendor: user-vendor\n");
    const result = await run(["status"], dirs);
    assert.equal(result.code, 0);
    assert.match(result.stdout, /vendor:\s*user-vendor/);
    assert.match(result.stdout, /source:\s*user/);
  });

  it("use without vendor exits non-zero", async () => {
    const result = await run(["use"], dirs);
    assert.notEqual(result.code, 0);
    assert.match(result.stderr, /vendor/);
  });

  it("unknown command exits non-zero", async () => {
    const result = await run(["wat"], dirs);
    assert.notEqual(result.code, 0);
  });
});
