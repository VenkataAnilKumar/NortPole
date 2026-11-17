#!/usr/bin/env node
/**
 * Reads Sim's tool files (Apache-2.0, see integrations/NOTICE) with the TypeScript compiler and prints, as JSON, the
 * tools that can be said as NortPole data without losing a safety rule, and the reason for each one that cannot.
 *
 *   node extract.cjs <typescript-module-dir> <sim apps/sim dir> <service> [<service> ...]
 *
 * Nothing is executed or imported from Sim: the files are only parsed. Anything not recognised is skipped, never guessed.
 */
const fs = require("fs");
const path = require("path");
const ts = require(path.resolve(process.argv[2]));
const SIM = path.resolve(process.argv[3]);
const services = process.argv.slice(4);

class Skip extends Error {}
const skip = (why) => { throw new Skip(why); };

const prop = (obj, name) => {
  for (const p of obj.properties) {
    if (ts.isPropertyAssignment(p) || ts.isMethodDeclaration(p)) {
      const n = p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) ? p.name.text : null;
      if (n === name) return p;
    }
    if (ts.isShorthandPropertyAssignment(p) && p.name.text === name) return p;
  }
  return null;
};
const strOf = (n) => (n && (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) ? n.text : null);
const unparen = (n) => { while (n && (ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isNonNullExpression(n))) n = n.expression; return n; };

/** `params.x`, `params.x.trim()`, `params.x?.trim()`, `String(params.x)`, `encodeURIComponent(...)` of those -> "x". */
let CONSTS = {};
function paramRef(n) {
  n = unparen(n);
  if (ts.isPropertyAccessExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === "params") return n.name.text;
  if (ts.isCallExpression(n)) {
    const callee = unparen(n.expression);
    if (ts.isPropertyAccessExpression(callee) && ["trim", "toString"].includes(callee.name.text) && n.arguments.length === 0) return paramRef(callee.expression);
    if (ts.isIdentifier(callee) && ["String", "encodeURIComponent"].includes(callee.text) && n.arguments.length === 1) return paramRef(n.arguments[0]);
    // Sim's own helper that checks a path segment; NortPole's executor encodes path values itself.
    if (ts.isIdentifier(callee) && callee.text === "safeUrlPathSegment" && n.arguments.length >= 1) return paramRef(n.arguments[0]);
  }
  return null;
}
/** `params.x ?? literal` -> { name, fallback }. */
function withFallback(n) {
  n = unparen(n);
  if (ts.isBinaryExpression(n) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(n.operatorToken.kind)) {
    const name = paramRef(n.left);
    const r = unparen(n.right);
    let fb;
    if (strOf(r) !== null) fb = strOf(r);
    else if (ts.isNumericLiteral(r) && /^\d+$/.test(r.text)) fb = Number(r.text);
    else if (r.kind === ts.SyntaxKind.TrueKeyword) fb = true;
    else if (r.kind === ts.SyntaxKind.FalseKeyword) fb = false;
    if (name && fb !== undefined) return { name, fallback: fb };
  }
  return null;
}
function placeholderText(n, used) {
  // A string or template whose every substitution is a parameter reference -> text with {name}.
  n = unparen(n);
  const s = strOf(n);
  if (s !== null) { if (s.includes("{") || s.includes("}")) skip("a literal brace in text"); return s; }
  if (ts.isTemplateExpression(n)) {
    let out = n.head.text;
    for (const span of n.templateSpans) {
      const name = paramRef(span.expression);
      const ex = unparen(span.expression);
      if (!name && ts.isIdentifier(ex) && CONSTS[ex.text] !== undefined) { out += CONSTS[ex.text] + span.literal.text; continue; }
      if (!name) skip("a computed value inside a template");
      used.add(name);
      out += `{${name}}` + span.literal.text;
    }
    if (out.replace(/\{\w+\}/g, "").match(/[{}]/)) skip("a literal brace in text");
    return out;
  }
  return null;
}

function functionBodyExpr(fn) {
  // (params) => expr   |   (params) => { ...; return expr }
  if (!fn || !(ts.isArrowFunction(fn) || ts.isFunctionExpression(fn) || ts.isMethodDeclaration(fn))) return { expr: fn, stmts: [] };
  if (!ts.isBlock(fn.body)) return { expr: fn.body, stmts: [] };
  const stmts = [...fn.body.statements];
  const last = stmts[stmts.length - 1];
  if (!last || !ts.isReturnStatement(last)) skip("a function that does not end in a return");
  return { expr: last.expression, stmts: stmts.slice(0, -1) };
}

/** A condition that only asks whether parameters are present: `params.x`, `params.x !== undefined`, `!= null`, joined by &&. */
function isPresenceGuard(cond) {
  const t = cond.getText().replace(/\s+/g, " ");
  return /^(!?params\.\w+(\s*(!==|!=)\s*(undefined|null|''))?)(\s*&&\s*!?params\.\w+(\s*(!==|!=)\s*(undefined|null|''))?)*$/.test(t) && !t.includes("!params");
}

function parseUrl(reqObj, used) {
  const p = prop(reqObj, "url");
  if (!p) skip("no address");
  const init = ts.isPropertyAssignment(p) ? p.initializer : p;
  const { expr, stmts } = functionBodyExpr(init);
  const e = unparen(expr);
  const direct = placeholderText(e, used);
  if (direct !== null && stmts.length === 0) return { url: direct, query: {} };
  // The block form: const url = `...`; const queryParams = new URLSearchParams(); if (params.x) queryParams.append('k', params.x); return qs ? `${url}?${qs}` : url
  let base = null; const query = {}; let sawParams = false;
  for (const st of stmts) {
    if (ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) {
        if (!d.initializer) continue;
        const ini = unparen(d.initializer);
        if (ts.isNewExpression(ini) && ini.expression.getText() === "URLSearchParams" && !ini.arguments?.length) { sawParams = true; continue; }
        const t = placeholderText(ini, used);
        if (t !== null && /^https:\/\//.test(t) && base === null) { base = t; continue; }
        if (ts.isCallExpression(ini) && ini.expression.getText().endsWith(".toString")) continue;
        skip("a computed value before the address is built");
      }
    } else if (ts.isExpressionStatement(st) && ts.isCallExpression(st.expression) && /^\w+\.(append|set)$/.test(st.expression.expression.getText())) {
      const call = st.expression;
      if (call.arguments.length === 2 && strOf(call.arguments[0]) !== null && paramRef(call.arguments[1])) { used.add(paramRef(call.arguments[1])); query[strOf(call.arguments[0])] = `{${paramRef(call.arguments[1])}}`; }
      else skip("a computed query value");
    } else if (ts.isIfStatement(st) && !st.elseStatement) {
      if (!isPresenceGuard(st.expression)) skip("a query value that depends on a condition");
      const stmt = ts.isBlock(st.thenStatement) ? st.thenStatement.statements : [st.thenStatement];
      for (const s2 of stmt) {
        if (ts.isExpressionStatement(s2) && ts.isCallExpression(s2.expression)) {
          const call = s2.expression;
          const m = call.expression.getText().match(/^(\w+)\.(append|set)$/);
          if (m && call.arguments.length === 2 && strOf(call.arguments[0]) !== null) {
            const name = paramRef(call.arguments[1]);
            if (!name) skip("a computed query value");
            used.add(name);
            query[strOf(call.arguments[0])] = `{${name}}`;
            continue;
          }
        }
        skip("a condition that does more than add a query value");
      }
    } else skip("a statement in the address function that is not a plain assignment");
  }
  if (base === null && sawParams && ts.isTemplateExpression(e) && e.templateSpans.length === 1 && /\.toString\(\)$/.test(e.templateSpans[0].expression.getText()) && e.head.text.startsWith("https://") && e.head.text.endsWith("?") && !e.templateSpans[0].literal.text) {
    return { url: e.head.text.slice(0, -1), query };
  }
  if (base === null || !sawParams) {
    if (direct !== null) return { url: direct, query };
    skip("a computed address");
  }
  // The final return must be the base with the query string, nothing else.
  return { url: base, query };
}

function objectLiteral(n, label) {
  n = unparen(n);
  if (!n || !ts.isObjectLiteralExpression(n)) skip(`${label} is not a plain object`);
  return n;
}

function parseHeaders(reqObj, used) {
  const p = prop(reqObj, "headers");
  const headers = {}; let credential = null;
  if (!p) return { headers, credential };
  const init = ts.isPropertyAssignment(p) ? p.initializer : p;
  const { expr, stmts } = functionBodyExpr(init);
  for (const st of stmts) {
    // Only guard clauses that throw when a token is missing.
    if (!(ts.isIfStatement(st) && !st.elseStatement && /throw/.test(st.thenStatement.getText()))) skip("header code other than a missing-token check");
  }
  const obj = objectLiteral(expr, "the headers");
  for (const hp of obj.properties) {
    if (!ts.isPropertyAssignment(hp)) skip("a computed header");
    const key = hp.name.text;
    const v = unparen(hp.initializer);
    const bearer = ts.isTemplateExpression(v) && v.head.text === "Bearer " && v.templateSpans.length === 1 && !v.templateSpans[0].literal.text
      ? paramRef(v.templateSpans[0].expression) : null;
    if (key === "Authorization" && bearer === "accessToken") { headers[key] = "Bearer {credential.access_token}"; credential = "oauth"; }
    else if (key === "Authorization" && bearer === "apiKey") { headers[key] = "Bearer {credential.api_key}"; credential = "api_key"; }
    else if (strOf(v) !== null && !/[{}]/.test(strOf(v)) && !/^(authorization|cookie|x-api-key)$/i.test(key)) headers[key] = strOf(v);
    else skip(`header ${key} is not a fixed value or the bearer token`);
  }
  return { headers, credential };
}

function bodyNode(n, defaults) {
  n = unparen(n);
  const s = strOf(n);
  if (s !== null) { if (/[{}]/.test(s)) skip("a brace in a body text"); return s; }
  if (n.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (n.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (n.kind === ts.SyntaxKind.NullKeyword) return null;
  if (ts.isNumericLiteral(n)) { if (!/^\d+$/.test(n.text)) skip("a decimal number in a body"); return Number(n.text); }
  if (ts.isPrefixUnaryExpression(n) && n.operator === ts.SyntaxKind.MinusToken && ts.isNumericLiteral(n.operand) && /^\d+$/.test(n.operand.text)) return -Number(n.operand.text);
  const fb = withFallback(n);
  if (fb) { defaults[fb.name] = fb.fallback; return `{${fb.name}}`; }
  const ref = paramRef(n);
  if (ref) return `{${ref}}`;
  if (ts.isArrayLiteralExpression(n)) return n.elements.map((e) => bodyNode(e, defaults));
  if (ts.isObjectLiteralExpression(n)) {
    const out = {};
    for (const p of n.properties) {
      if (!ts.isPropertyAssignment(p) && !ts.isShorthandPropertyAssignment(p)) skip("a spread or method in a body");
      const key = p.name.text;
      out[key] = ts.isShorthandPropertyAssignment(p) ? skip("a shorthand body value") : bodyNode(p.initializer, defaults);
    }
    return out;
  }
  skip("a computed value in a body");
}
function parseBody(reqObj, used) {
  const p = prop(reqObj, "body");
  if (!p) return { body: null, defaults: {} };
  const init = ts.isPropertyAssignment(p) ? p.initializer : p;
  const { expr, stmts } = functionBodyExpr(init);
  const defaults = {};
  const e = unparen(expr);
  if (ts.isCallExpression(e) && /JSON\.stringify/.test(e.expression.getText())) skip("a body built with JSON.stringify");
  let local = null, localName = null;
  const sets = [];
  for (const st of stmts) {
    if (ts.isVariableStatement(st) && st.declarationList.declarations.length === 1 && !local) {
      const d = st.declarationList.declarations[0];
      if (d.initializer && ts.isObjectLiteralExpression(unparen(d.initializer))) { localName = d.name.getText(); local = bodyNode(unparen(d.initializer), defaults); continue; }
    }
    const one = ts.isIfStatement(st) && !st.elseStatement && isPresenceGuard(st.expression) ? st.thenStatement : st;
    const inner = ts.isBlock(one) ? (one.statements.length === 1 ? one.statements[0] : null) : one;
    if (local && inner && ts.isExpressionStatement(inner) && ts.isBinaryExpression(inner.expression) && inner.expression.operatorToken.kind === ts.SyntaxKind.EqualsToken
        && ts.isPropertyAccessExpression(inner.expression.left) && inner.expression.left.expression.getText() === localName) {
      local[inner.expression.left.name.text] = bodyNode(inner.expression.right, defaults);
      continue;
    }
    skip("code before the body is built");
  }
  if (stmts.length && !local) skip("code before the body is built");
  const resolve = (n) => {
    n = unparen(n);
    if (local && ts.isIdentifier(n) && n.text === localName) return local;
    if (local && ts.isObjectLiteralExpression(n)) {
      const out = {};
      for (const p of n.properties) {
        if (ts.isShorthandPropertyAssignment(p) && p.name.text === localName) out[p.name.text] = local;
        else if (ts.isPropertyAssignment(p)) { const v = unparen(p.initializer); out[p.name.text] = ts.isIdentifier(v) && v.text === localName ? local : bodyNode(v, defaults); }
        else skip("a spread or method in a body");
      }
      return out;
    }
    return bodyNode(objectLiteral(n, "the body"), defaults);
  };
  const body = resolve(e);
  const walk = (x) => { if (typeof x === "string") for (const m of x.matchAll(/\{(\w+)\}/g)) used.add(m[1]); else if (x && typeof x === "object") Object.values(x).forEach(walk); };
  walk(body);
  return { body, defaults };
}

const PARAM_TYPE = { string: "string", number: "integer", boolean: "boolean", json: "object", object: "object" };
function parseParams(obj) {
  const p = prop(obj, "params");
  const out = {};
  if (!p) return out;
  const lit = objectLiteral(p.initializer, "params");
  for (const q of lit.properties) {
    if (!ts.isPropertyAssignment(q)) skip("a computed parameter");
    const name = q.name.text;
    const d = objectLiteral(q.initializer, `parameter ${name}`);
    const get = (k) => { const x = prop(d, k); return x && ts.isPropertyAssignment(x) ? x.initializer : null; };
    const vis = strOf(get("visibility"));
    if (name === "accessToken" || name === "apiKey") continue;
    if (vis === "hidden") skip(`parameter ${name} is set by the platform`);
    const type = PARAM_TYPE[strOf(get("type"))];
    if (!type) skip(`parameter ${name} has a type this importer does not carry (${strOf(get("type"))})`);
    out[name] = {
      type, required: get("required")?.kind === ts.SyntaxKind.TrueKeyword,
      fill: { "user-only": "user", "llm-only": "model" }[vis] || "user_or_model",
      description: strOf(get("description")) ?? (() => { const t = get("description"); return t ? placeholderText(t, new Set()) : null; })() ?? name,
    };
  }
  return out;
}

const OUT_TYPE = { string: "string", number: "number", boolean: "boolean", array: "array", json: "object", object: "object" };
function dataPath(n, dataVar, alias = {}) {
  n = unparen(n);
  const fb = ts.isBinaryExpression(n) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(n.operatorToken.kind);
  if (fb) return dataPath(n.left, dataVar, alias);
  if (ts.isIdentifier(n) && n.text === dataVar) return "$";
  if (ts.isIdentifier(n) && alias[n.text] !== undefined) return alias[n.text];
  if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)) {
    const inner = dataPath(n.expression, dataVar, alias);
    if (inner === null) return null;
    if (ts.isPropertyAccessExpression(n)) return `${inner}.${n.name.text}`;
    const a = unparen(n.argumentExpression);
    if (ts.isNumericLiteral(a) && /^\d{1,3}$/.test(a.text)) return `${inner}[${a.text}]`;
    if (strOf(a) !== null && /^[A-Za-z_]\w*$/.test(strOf(a))) return `${inner}.${strOf(a)}`;
    return null;
  }
  return null;
}
function parseOutputs(obj, src) {
  const t = prop(obj, "transformResponse");
  if (!t) skip("no response mapping");
  const text = t.getText(src);
  if (/response\.text\(\)|response\.arrayBuffer\(\)|response\.blob\(\)|\.headers\.get/.test(text)) skip("the response is not JSON");
  const m = text.match(/const\s+(\w+)\s*=\s*await\s+response\.json\(\)/);
  if (!m) skip("the response is not read as JSON in one step");
  const dataVar = m[1];
  const declared = {};
  const o = prop(obj, "outputs");
  const typeFiles = [src, ...(["types.ts"].map((f) => path.join(path.dirname(src.fileName), f)).filter((f) => fs.existsSync(f)).map((f) => ts.createSourceFile(f, fs.readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true)))];
  const lookup = (name) => {
    for (const sf of typeFiles) {
      let found = null;
      sf.forEachChild((st) => { if (ts.isVariableStatement(st)) for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name) && d.name.text === name && d.initializer && ts.isObjectLiteralExpression(unparen(d.initializer))) found = unparen(d.initializer); });
      if (found) return found;
    }
    return null;
  };
  const describe = (lit) => {
    for (const q of lit.properties) {
      if (!ts.isPropertyAssignment(q)) continue;
      let v = unparen(q.initializer);
      if (ts.isIdentifier(v)) v = lookup(v.text) ?? v;
      if (!ts.isObjectLiteralExpression(v)) continue;
      const ty = prop(v, "type"), ds = prop(v, "description");
      declared[q.name.text] = { type: OUT_TYPE[strOf(ty?.initializer)], description: strOf(ds?.initializer) ?? q.name.text };
    }
  };
  if (o) {
    let lit = unparen(o.initializer);
    if (ts.isIdentifier(lit)) lit = lookup(lit.text);
    if (lit && ts.isObjectLiteralExpression(lit)) describe(lit);
  }
  // The success return: the last `output: { ... }` object in the mapping.
  let outObj = null;
  const visit = (n) => {
    if (ts.isPropertyAssignment(n) && n.name.text === "output" && ts.isObjectLiteralExpression(n.initializer) && n.initializer.properties.length) outObj = n.initializer;
    ts.forEachChild(n, visit);
  };
  visit(t);
  if (!outObj) skip("no output object in the response mapping");
  const outputs = {}; const dropped = [];
  // `const record = data.data` style names for parts of the response.
  const alias = {};
  const collect = (n) => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && n.name.text !== dataVar) {
      const p = dataPath(n.initializer, dataVar, alias);
      if (p !== null) alias[n.name.text] = p;
    }
    ts.forEachChild(n, collect);
  };
  collect(t);
  for (const q of outObj.properties) {
    const isShort = ts.isShorthandPropertyAssignment(q);
    if (!ts.isPropertyAssignment(q) && !isShort) { dropped.push("(computed)"); continue; }
    const name = q.name.text;
    const p = dataPath(isShort ? q.name : q.initializer, dataVar, alias);
    if (p !== null && declared[name] === undefined) { /* no declared type: dropped below */ }
    const d = declared[name];
    if (p === null || !d || !d.type) { dropped.push(name); continue; }
    outputs[name] = { path: p, type: d.type, description: d.description };
  }
  if (!Object.keys(outputs).length) skip("no output can be read from the response by name");
  return { outputs, dropped };
}

const READ_WORDS = /^(get|list|search|read|find|lookup|query|check|retrieve|fetch|describe|count|batch_read|download_metadata)(_|$)/;
function effectOf(method, shortId) {
  if (method === "GET") return "read";
  if (method === "POST") return READ_WORDS.test(shortId) ? "read" : "write";
  return "write";
}

function parseTool(file, service) {
  const src = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
  let obj = null;
  src.forEachChild((st) => {
    if (!ts.isVariableStatement(st)) return;
    for (const d of st.declarationList.declarations) {
      if (d.type && d.type.getText(src).startsWith("ToolConfig") && d.initializer && ts.isObjectLiteralExpression(d.initializer)) obj = d.initializer;
    }
  });
  if (!obj) skip("not a tool definition");
  CONSTS = {};
  src.forEachChild((st) => {
    if (!ts.isVariableStatement(st) || !(st.declarationList.flags & ts.NodeFlags.Const)) return;
    for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name) && d.initializer && strOf(d.initializer) !== null && !/[{}`$]/.test(strOf(d.initializer))) CONSTS[d.name.text] = strOf(d.initializer);
  });
  const id = strOf(prop(obj, "id")?.initializer), name = strOf(prop(obj, "name")?.initializer), description = strOf(prop(obj, "description")?.initializer);
  if (!id || !name || !description) skip("no plain id, name or description");
  const req = prop(obj, "request");
  if (!req || !ts.isObjectLiteralExpression(req.initializer)) skip("no request block");
  const reqObj = req.initializer;
  if (prop(obj, "directExecution") || prop(obj, "postProcess")) skip("runs code of its own");
  const method = strOf(prop(reqObj, "method")?.initializer);
  if (!["GET", "POST", "PUT", "PATCH", "DELETE"].includes(method)) skip(`method ${method} is not carried`);
  const used = new Set();
  const { url, query } = parseUrl(reqObj, used);
  const { headers, credential } = parseHeaders(reqObj, used);
  const { body, defaults } = parseBody(reqObj, used);
  if (method === "GET" && body) skip("a GET with a body");
  if (method === "DELETE" && body) skip("a DELETE with a body");
  const host = (url.match(/^https:\/\/([a-z0-9.\-]+)(?:[/?]|$)/) || [])[1];
  if (!host) skip("the host is not fixed");
  const params = parseParams(obj);
  Object.values(query).forEach((v) => used.add(v.slice(1, -1)));
  for (const u of used) if (!params[u]) skip(`the request uses ${u}, which is not a declared parameter`);
  for (const [k, v] of Object.entries(defaults)) if (params[k] && typeof v === { string: "string", integer: "number", boolean: "boolean" }[params[k].type]) params[k].default = v;
  const oauth = prop(obj, "oauth");
  let provider = null;
  if (oauth && ts.isObjectLiteralExpression(oauth.initializer)) provider = strOf(prop(oauth.initializer, "provider")?.initializer);
  if (credential === "oauth" && !provider) skip("a bearer token without a sign-in provider");
  if (credential === null && (oauth || prop(obj, "params")?.getText(src).includes("accessToken"))) skip("a sign-in that the request never sends");
  const { outputs, dropped } = parseOutputs(obj, src);
  const shortId = id.replace(new RegExp(`^${service}_`), "");
  return {
    file: path.basename(file), id: shortId, name: name.replace(new RegExp(`^${service.replace(/_/g, " ")}\\s+`, "i"), "").replace(/\s+(in|from|to|on|with|for)\s+[A-Z][\w ]*$/, "") || name, description,
    effect: effectOf(method, shortId), method, url, query, headers, body, params, outputs, dropped, credential, provider, host,
  };
}

function blockInfo(service) {
  const dir = path.join(SIM, "blocks", "blocks");
  for (const f of fs.readdirSync(dir)) {
    if (f !== `${service}.ts` && !f.startsWith(`${service}_`) ) continue;
    const text = fs.readFileSync(path.join(dir, f), "utf8");
    const name = (text.match(/^\s{2}name:\s*'([^']+)'/m) || [])[1];
    const type = (text.match(/integrationType:\s*IntegrationType\.(\w+)/) || [])[1];
    const desc = (text.match(/^\s{2}description:\s*\n?\s*'([^']+)'/m) || [])[1];
    if (name) return { name, type, description: desc };
  }
  return {};
}

const result = {};
for (const service of services) {
  const dir = path.join(SIM, "tools", service);
  if (!fs.existsSync(dir)) { result[service] = { error: "no such folder" }; continue; }
  const tools = [], skipped = [];
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.endsWith(".ts") || f.endsWith(".test.ts") || f === "index.ts" || f === "types.ts") continue;
    try { tools.push(parseTool(path.join(dir, f), service)); }
    catch (e) { if (e instanceof Skip) skipped.push({ file: f, why: e.message }); else throw e; }
  }
  result[service] = { block: blockInfo(service), tools, skipped };
}
process.stdout.write(JSON.stringify(result, null, 1));
