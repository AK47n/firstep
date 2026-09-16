/* 生成"要从历史里删掉的文件"的精确清单。
 *
 * 为什么不直接在 filter-branch 的脚本里写正则：
 *   ① filter-branch 的 index-filter 是对**每个提交**跑的（这里 2777 个），
 *      里面再套一层"列文件 + 正则筛"会让本来几分钟的活变成几十分钟；
 *   ② 那种脚本要用 sh + tr + xargs，而这台机器上只有 git 自带的那套 Unix 工具，
 *      PowerShell 里跑不了 —— 调试起来很别扭；
 *   ③ 最要紧的是：**清单要先给人看过**。删错一个文件是不可逆的。
 *
 * 所以：在 Node 里算一次，写成一个文件；filter-branch 只负责"照着清单删"。
 *
 * 跑：node scripts/make-purge-list.mjs <仓库目录> [输出文件]
 */
import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

const repoDir = process.argv[2]
const outFile = process.argv[3] || 'scripts/purge-generated.list'
if (!repoDir) {
  console.error('用法：node scripts/make-purge-list.mjs <仓库目录> [输出文件]')
  process.exit(2)
}

const files = execFileSync('git', ['-C', repoDir, 'ls-files', '-z'], { maxBuffer: 256 * 1024 * 1024 })
  .toString('utf8')
  .split('\0')
  .filter(Boolean)

/* 规则：工具生成的产物。每一条都对应一次实际统计（见 audit-build-artifacts.mjs）。 */
const RULES = [
  { name: 'Keil Objects/（编译结果）', re: /(^|\/)Objects\// },
  { name: 'Keil Listings/（清单）', re: /(^|\/)Listings\// },
  { name: 'CCS Debug/（编译输出，含 SysConfig 生成文件）', re: /(^|\/)Debug\// },
  { name: 'CCS DebugConfig/', re: /(^|\/)DebugConfig\// },
  { name: 'IDE .settings/', re: /(^|\/)\.settings\// },
  { name: 'IDE .vscode/', re: /(^|\/)\.vscode\// },
  { name: 'clangd 索引缓存', re: /(^|\/)\.clangd\// },
  { name: 'Keil GUI 布局（文件名带用户名）', re: /\.uvguix\./ },
  { name: 'Keil 编译日志（含许可证/邮箱）', re: /\.build_log\.htm$/ },
  { name: 'TI linkInfo', re: /\.linkInfo\.xml$/ },
  { name: 'CCS 工程用户设置', re: /\.projectspec\.user$/ },
  { name: '调试器配置', re: /\.(scvd|lnp|iex|sct|opt)$/ },
]

/* 例外：**看着像 IDE 状态、其实是工程配置**的东西，不进清单（照删会坏生成物）。
 *
 * 为什么需要这一条（2026-09-16 补，踩过才知道）：
 *   `IDE .settings/` 那条规则把 `library/masters/mspm0/.settings/` 一起扫掉了，其中
 *   `org.eclipse.core.resources.prefs` 钉着 CCS 工程编码（`encoding/<project>=UTF-8`）——
 *   它不是可再生状态，是工程配置。当时**闸门没叫停**：闸门只认「像源码」的扩展名，
 *   而 `.prefs` 不在其中。半天后由 `tests/test_readme.py` 的母版同步守卫抓出来，
 *   而那条红在 main 上挂了一整天（详见 `tests/test_master_template_config.py` 顶部）。
 *
 * 判据：母版下的 `.settings/` 是「随母版分发给生成工程的配置」；其余位置的 `.settings/`
 * （用户工程、revise 备份）仍按 IDE 状态处理。
 */
const KEEP = [
  { name: '母版 .settings/ 工程配置（含 CCS 编码钉）', re: /^library\/masters\/[^/]+\/\.settings\// },
]

/* 绝不能**静默**删的扩展名：真源码 + 工程配置。命中这些就停下来报警，由人确认。
 * `.prefs` 是 2026-09-16 补的——它是 `.settings/` 的常见载体，当初漏在名单外，
 * 于是「规则过宽」没有任何东西兜住。 */
const SOURCE_EXT = /\.(c|h|s|py|md|js|mjs|json|syscfg|uvprojx|uvoptx|ioc|ld|icf|toml|ya?ml|txt|html?|prefs|ccsproject|cproject|project)$/i

const byRule = new Map()
const purged = new Set()
const kept = []
for (const f of files) {
  if (KEEP.some((k) => k.re.test(f))) {
    kept.push(f)
    continue
  }
  for (const { name, re } of RULES) {
    if (!re.test(f)) continue
    purged.add(f)
    if (!byRule.has(name)) byRule.set(name, [])
    byRule.get(name).push(f)
    break
  }
}

console.log(`\n  仓库：${repoDir}`)
console.log(`  跟踪文件 ${files.length} 个 → 命中 ${purged.size} 个 / 例外保留 ${kept.length} 个\n`)
for (const { name } of RULES) {
  const list = byRule.get(name) || []
  console.log(`      ${String(list.length).padStart(5)}  ${name}`)
}
if (kept.length) {
  console.log('\n  例外保留（工程配置，不删）：')
  for (const { name } of KEEP) {
    const list = files.filter((f) => KEEP.find((k) => k.name === name).re.test(f))
    console.log(`      ${String(list.length).padStart(5)}  ${name}`)
  }
}

// 安全闸：命中里有"像源码 / 像工程配置"的，列出来让人确认
const srcish = [...purged].filter((f) => SOURCE_EXT.test(f))
console.log(`\n  命中里"像源码或工程配置"的：${srcish.length} 个`)
for (const f of srcish.slice(0, 20)) console.log('      ' + f)

/* 自动判断：能不能放手删。
   Debug/ 下的 SysConfig 生成文件（ti_msp_dl_config.c/h）是**生成物**，
   只要对应的 .syscfg 还在就安全。这里把它查出来。 */
const risky = srcish.filter((f) => !/ti_msp_dl_config\.(c|h)$/i.test(f))
if (risky.length) {
  console.log(`\n  ⚠ 有 ${risky.length} 个命中不是"已知的生成文件"，请人工确认后再删：`)
  for (const f of risky.slice(0, 20)) console.log('      ' + f)
} else {
  console.log('  ✓ 像源码的全是 SysConfig 生成文件（源 .syscfg 在库里），可以删')
}

const content =
  '# 要从历史里删掉的文件（每行一个）。\n' +
  '# 由 scripts/make-purge-list.mjs 生成 —— 规则改了要重新生成。\n' +
  '# 用法见 scripts/purge-generated.sh。\n' +
  [...purged].sort().join('\n') +
  '\n'
writeFileSync(outFile, content, 'utf8')
console.log(`\n  清单已写入：${outFile}（${purged.size} 行）`)
process.exit(risky.length ? 1 : 0)
