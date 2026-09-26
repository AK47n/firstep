// probe-06-red.mjs 鈥?宸ュ崟 hwcheck-hygiene/06 鐨勫垽鎹己搴﹀弽璇侊紙涓ゅ娉ㄥ叆锛屽悇鑷窇瀹屽鍘燂級銆?//
// 鏈崟鐨勫垽鎹槸**杩愯鏃惰涓?*锛堢劍鐐硅惤鍦ㄥ摢銆佹寜閿敓涓嶇敓鏁堬級锛屾墍浠ュ弽璇佷篃鎵撳湪杩欎竴灞傦細
// 鐪熸祻瑙堝櫒 + 鐪熷悗绔窇閭ｆ潯鐢ㄤ緥锛岀湅瀹冩槸涓嶆槸鐪熺殑浼氱孩銆?//
//   路 **A 鎾ゆ帀鐒︾偣鎭㈠** 鈥斺€?`ui/hwcheck.js` 鐨?`renderHwcheckChecklist` 鏀跺熬涓嶅啀
//     `applyPendingFocus()`锛? 閲嶇粯鍚庣劍鐐规帀鍥?body 鐨勬棫褰㈡€侊級鈫?鐢ㄤ緥蹇呴』绾€?//   路 **B 鎾ゆ帀鍣ㄤ欢鍗＄殑閿洏鍙揪** 鈥斺€?`fx/module.js` 鐨勫崱鐗囧幓鎺?`role/tabindex`
//     锛? 璇勫璇寸殑"鍗＄墖鏄?div銆佹棤 tabindex / role / 閿洏"锛夆啋 鐢ㄤ緥蹇呴』绾€?//
// 姣忓鎸?*瀛楄妭**鏀瑰啓銆佽窇瀹岄€愬瓧鑺傚鍘熷苟澶嶆牳 sha256锛涢敋鐐规寜鏂囦欢瀹為檯鎹㈣褰㈡€佺紪鐮併€?//
// 鐢ㄦ硶锛歚node .scratch/hwcheck-hygiene/probe-06-red.mjs`
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const UI = `${REPO}src/contest_generator/static/js/ui/hwcheck.js`;
const FX = `${REPO}src/contest_generator/static/js/fx/module.js`;
const A11Y = `${REPO}src/contest_generator/static/js/ui/a11y.js`;
const SPEC = "tests/browser/hwcheck.spec.mjs";

const sha = (buf) => createHash("sha256").update(buf).digest("hex");

/** 鎸夋枃浠跺湪鐩樹笂鐨勬崲琛屽舰鎬佺紪鐮侀敋鐐癸紙鏈伐浣滄爲 LF / CRLF 娣疯锛夈€?*/
function encode(text, blob) {
  const newline = blob.toString("utf8").includes("\r\n") ? "\r\n" : "\n";
  return Buffer.from(text.replace(/\n/g, newline), "utf8");
}

function runSpec(pattern) {
  try {
    const out = execFileSync("node", ["--test", "--test-concurrency=1",
      `--test-name-pattern=${pattern}`, SPEC], { cwd: REPO, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { code: 0, out };
  } catch (e) {
    return { code: e.status === undefined ? 1 : e.status, out: `${e.stdout || ""}${e.stderr || ""}` };
  }
}

const CASES = [
  {
    label: "A 鎾ゆ帀鐒︾偣鎭㈠锛堥噸缁樺悗涓嶅啀鍥炵劍鐐癸級",
    file: UI,
    from: "    + hwcheckChecklistHTML(items, hwcheckUI.checklistChecked);\n  applyPendingFocus();\n}",
    to: "    + hwcheckChecklistHTML(items, hwcheckUI.checklistChecked);\n}",
  },
  {
    label: "B 鎾ゆ帀鍣ㄤ欢鍗＄殑閿洏鍙揪锛坮ole/tabindex 鎷挎帀锛?,
    file: FX,
    from: "' role=\"button\" tabindex=\"0\"'\n      + ' title=\"'",
    to: "''\n      + ' title=\"'",
    pattern: "鐒︾偣涓庡彲杈炬€?,
  },
  {
    label: "C 鎾ゆ帀涓€涓緭鍏ョ殑鍙闂悕锛堟爣绛捐〃閲屽幓鎺夋悳绱㈡閭ｆ潯锛?,
    file: A11Y,
    from: '  "hwcheck-device-search": "鎼滅储瑕佹祴鐨勫櫒浠?,\n',
    to: "",
    pattern: "鏃犻殰纰嶅悕",
  },
];

const lines = [];
const say = (t = "") => lines.push(t);
let allOk = true;

for (const item of CASES) {
  const original = readFileSync(item.file);
  const digest = sha(original);
  say(`=== ${item.label} ===`);
  say(`鐩爣锛?{item.file.slice(REPO.length).replace(/\\/g, "/")}  鍓嶇疆 sha256锛?{digest}`);
  const from = encode(item.from, original);
  const to = encode(item.to, original);
  if (original.indexOf(from) < 0) {
    say("鉁?鍓嶇疆妫€鏌ヤ笉閫氳繃锛氭柊褰㈡€侀敋鐐规壘涓嶅埌 鈥斺€?鏈敼鍔ㄤ换浣曞瓧鑺?);
    allOk = false;
    continue;
  }
  let redOk = false;
  const pattern = item.pattern || "鐒︾偣涓庡彲杈炬€?;
  try {
    // 鎸?*瀛楄妭**鏇挎崲锛堥敋鐐规寜鏂囦欢瀹為檯鎹㈣缂栫爜锛夆€斺€旂敤瀛楃涓?replace 浼氬湪 CRLF 鏂囦欢涓婇潤榛樹笉涓?    const at = original.indexOf(from);
    writeFileSync(item.file, Buffer.concat([original.subarray(0, at), to, original.subarray(at + from.length)]));
    say(`娉ㄥ叆鍚?sha256锛?{sha(readFileSync(item.file))}锛堝簲涓嶇瓑浜庡墠缃€硷級`);
    const { code, out } = runSpec(pattern);
    const failed = /^鈩?fail (\d+)$/m.exec(out.replace(/\r/g, ""));
    const failCount = failed ? Number(failed[1]) : -1;
    redOk = code !== 0 && failCount > 0 && out.includes(pattern);
    say(`娉ㄥ叆鎬侊細閫€鍑虹爜 ${code} / fail ${failCount}锛涖€?{pattern}銆嶉偅鏉℃姤绾細${redOk ? "鉁? : "鉁?}`);
    if (redOk) {
      const line = out.split("\n").find((l) => l.startsWith("鉁?) && l.includes(pattern));
      if (line) say(`  ${line.trim()}`);
    }
  } finally {
    writeFileSync(item.file, original);
  }
  const after = sha(readFileSync(item.file));
  say(`澶嶅師 sha256锛?{after}  閫愬瓧鑺傜浉鍚岋細${after === digest ? "鉁? : "鉁?}`);
  const green = runSpec(pattern);
  const ok = redOk && after === digest && green.code === 0;
  say(`澶嶅師鎬侊細閫€鍑虹爜 ${green.code}  鍥炵豢锛?{green.code === 0 ? "鉁? : "鉁?}`);
  say("");
  allOk = allOk && ok;
}

say(`缁撹锛?{allOk ? "PASS 鈥斺€?涓ゅ鍒ゆ嵁閮芥湁寮哄害锛屼笖鎺㈤拡鏈暀涓嬩换浣曟敼鍔? : "FAIL"}`);
const text = `${lines.join("\n")}\n`;
writeFileSync(`${REPO}.scratch/hwcheck-hygiene/probe-06-red.txt`, text, "utf8");
process.stdout.write(text);
process.exit(allOk ? 0 : 1);
