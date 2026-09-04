"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const CONFIG_NAME = ".api-test-skills.yaml";
const VENDOR_RE = /^[a-zA-Z0-9][a-zA-Z0-9_-]*$/;

const HELP = `api-test-skills — 写入 vendor 配置

用法:
  npx api-test-skills use <vendor>           写 ~/.api-test-skills.yaml
  npx api-test-skills use <vendor> --project 写 ./.api-test-skills.yaml
  npx api-test-skills use none               关闭适配
  npx api-test-skills status                 打印当前生效的 vendor 及来源
`;

function resolveDirs(opts = {}) {
  return {
    cwd: opts.cwd || process.cwd(),
    homedir: opts.homedir || os.homedir(),
  };
}

function paths(dirs) {
  return {
    project: path.join(dirs.cwd, CONFIG_NAME),
    user: path.join(dirs.homedir, CONFIG_NAME),
  };
}

function parseVendor(content) {
  if (!content) return null;
  const match = content.match(/^[ \t]*vendor:[ \t]*(\S+)[ \t]*$/m);
  if (!match) return null;
  return match[1];
}

function readVendor(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return parseVendor(fs.readFileSync(filePath, "utf8"));
}

function writeVendor(filePath, vendor) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `vendor: ${vendor}\n`, "utf8");
}

function resolveEffective(dirs) {
  const { project, user } = paths(dirs);
  const projectVendor = readVendor(project);
  if (projectVendor !== null) {
    return { vendor: projectVendor, source: "project", path: project };
  }
  const userVendor = readVendor(user);
  if (userVendor !== null) {
    return { vendor: userVendor, source: "user", path: user };
  }
  return { vendor: "none", source: "未配置", path: null };
}

function normalizeVendor(raw) {
  if (!raw) return { error: "缺少 vendor。用法: api-test-skills use <vendor> [--project]" };
  const vendor = String(raw).trim();
  if (!VENDOR_RE.test(vendor)) {
    return {
      error: `非法 vendor 名 ${JSON.stringify(raw)}。只允许字母数字、连字符、下划线，且以字母或数字开头。`,
    };
  }
  return { vendor: vendor.toLowerCase() === "none" ? "none" : vendor };
}

async function main(argv, opts = {}) {
  const dirs = resolveDirs(opts);
  const args = [...argv];
  const out = { code: 0, stdout: "", stderr: "" };

  const cmd = args.shift();
  if (!cmd || cmd === "-h" || cmd === "--help" || cmd === "help") {
    out.stdout = HELP;
    return out;
  }

  if (cmd === "status") {
    const effective = resolveEffective(dirs);
    const lines = [`vendor: ${effective.vendor}`, `source: ${effective.source}`];
    if (effective.path) lines.push(`path: ${effective.path}`);
    out.stdout = lines.join("\n") + "\n";
    return out;
  }

  if (cmd === "use") {
    const projectFlag = args.includes("--project");
    const vendorArg = args.find((a) => a !== "--project");
    const parsed = normalizeVendor(vendorArg);
    if (parsed.error) {
      out.code = 1;
      out.stderr = parsed.error + "\n";
      return out;
    }
    const target = projectFlag ? paths(dirs).project : paths(dirs).user;
    writeVendor(target, parsed.vendor);
    out.stdout = `已写入 ${target}（vendor: ${parsed.vendor}）\n`;
    return out;
  }

  out.code = 1;
  out.stderr = `未知命令 ${cmd}。\n${HELP}`;
  return out;
}

module.exports = { main, HELP };
