// fx/pin-model.js — 引脚判据模型的前端**求值**（工单 gen-chain-audit/05）。
//
// 判据单源：模型由后端 `POST /api/bindings/matrix` 下发
// （`pin_bindings.build_bindings_matrix`，与生成/校验同一批门禁规则算出）。
// 本模块**不含任何后端规则**——只有两件事：
//   ① 命中 `selectable`（后端的能力层：类型 / 实例 / 通道前缀全算好了）；
//   ② 求值 `constraint` 谓词（跨角色：端口组 / pwm 两通道同实例 / 槽位互斥）。
// 这是工单 03 那 115 条「板图显示可绑、生成必 400」的根治口径：前端不再照抄
// `pin_bindings` 的类型级 / 通道 / 成对规则，后端加门禁时板图自动跟上。
//
// 模型形状（后端契约见 webapp `/api/bindings/matrix` 文档串）：
//   {roles: [{role, type, default, selectable: [PIN...], constraint[, constraints]}]}
//   constraint  = null | {kind:"port", port:"B", reason}
//                       | {kind:"instance", instances:[...], pair, reason}
//                       | {kind:"slot", pin:"PB6", peers:["<slug>.<role>"], reason}
//   constraints = 多条谓词**并存**时的数组（元素同 constraint；全部成立才可绑）。
//   判据是「并列的独立门禁」而不是「选一条」：`as32.AS32_UART_TX` 既有 uart 对脚
//   （实例谓词），又与 `zigbee_link.ZIGBEE_UART_TX` 默认同 PA26（槽位谓词）——
//   单条 `constraint` 字段装不下两条，只发前者就漏掉后者（工单 04 实测 37 条）。
//
// **成对角色要「一起搬」（工单 mspm0-slot-conflict/05）**：后端 `_check_paired_role_instances`
// 的语义是「成对角色（uart TX/RX、i2c SCL/SDA、pwm C0/C1）的两脚有效实例集交集非空」，
// 看的是**整份 bindings**——所以「只搬 TX 到 UART0、RX 留在 UART2」必 400。而界面
// 原本是**单角色绑一脚**（`bindRole` 一次写一个 key），用户走不出第一步（工单 04
// 把模型改成严格镜像后记的账：188+52 条假绿归零，代价是这条交互缺口）。
// 补法：本模块给「点候选脚时**对脚跟到哪**」一个确定解（`pinPairFollow`），
// 判据求值把「对脚跟得上」也算成立；`ui/generate-pins.js` 在同一次提交里写两个 key。
// **不动任何后端判据**（谓词语义 / 门禁一字不动）——只是让用户能一次把两脚搬到同实例。

/** 模型里某角色（`<slug>.<role_id>`）的条目；模型未到 / 无该角色 → null。 */
export function pinModelEntry(model, roleKey) {
  if (!model || !Array.isArray(model.roles)) return null;
  return model.roles.find((r) => r && r.role === roleKey) || null;
}

/**
 * 某角色的**全部**适用谓词（后端 `constraint` / `constraints` 的读取口径）。
 *
 * 单源收敛在这里：`constraints` 是数组（多条并存）时用它，否则用单条 `constraint`。
 * 前端别处不许再各读一次（两处口径 = 迟早漂移）。
 */
export function pinModelConstraints(entry) {
  if (!entry) return [];
  const many = entry.constraints;
  if (Array.isArray(many) && many.length) return many.filter(Boolean);
  return entry.constraint ? [entry.constraint] : [];
}

/** 从引脚能力 token 取某类型的实例名（`pwm:TIMG0_C0` + `pwm` → `TIMG0_C0`）。 */
export function pinInstanceTokens(pin, type) {
  const prefix = type + ":";
  return ((pin && pin.capabilities) || [])
    .filter((t) => typeof t === "string" && t.startsWith(prefix))
    .map((t) => t.slice(prefix.length));
}

/** 角色/引脚角色键的 pwm 通道尾（`motor.PWMAB_C0` → `"C0"`；无 → null）。 */
export function pinRoleChannel(roleKey) {
  const id = String(roleKey || "").split(".").pop() || "";
  const m = id.match(/_C(\d+)$/);
  return m ? "C" + m[1] : null;
}

/** 谓词是否「成对实例」那一条（唯一会被「对脚跟随」满足的 kind）。 */
function isPairConstraint(c) {
  return !!c && c.kind === "instance" && typeof c.pair === "string" && c.pair;
}

/**
 * 单条谓词的求值（`pinModelVerdict` 的内部件，也供单测直接钉）。
 *
 * - `port` 比端口字母；`slot` 比引脚名相等（同槽位同伴当前有效脚，后端
 *   `_check_slot_conflicts` 同判据）；
 * - `instance` 比实例集——**两脚各自先按本脚通道过滤再取实例基名比交集**
 *   （与后端 `_check_mspm0_pwm_channel_pairs` 逐字同口径：本脚通道取自己的角色键尾、
 *   对脚通道取 `constraint.pair` 键尾）。少了通道过滤就会把 `TIMA0_C0` 与对脚的
 *   互补通道 `TIMA0_C3N` 算成同实例（24 条假绿）；**非 pwm**（uart TX/RX、
 *   i2c SCL/SDA）按实例名**精确**比（后端 `_check_paired_role_instances` 同口径）；
 * - 未识别的 kind 保守放行（新 kind 由后端先行、前端跟上）。
 */
export function pinConstraintHolds(constraint, entry, roleKey, pin) {
  const c = constraint;
  if (!c) return true;
  if (c.kind === "port") return pin.name[1] === c.port;
  if (c.kind === "slot") return !c.pin || pin.name === c.pin;
  if (c.kind === "instance") {
    const wanted = Array.isArray(c.instances) ? c.instances : [];
    if (!wanted.length) return true;
    if (entry.type !== "pwm") {
      return pinInstanceTokens(pin, entry.type).some((i) => wanted.includes(i));
    }
    const own = pinRoleChannel(roleKey);
    const mate = pinRoleChannel(c.pair);
    const base = (i) => String(i).split("_")[0];
    const pick = (list, channel) => list.filter(
      (i) => !channel || String(i).endsWith("_" + channel),
    ).map(base);
    const mine = pick(pinInstanceTokens(pin, entry.type), own);
    return mine.some((i) => pick(wanted, mate).includes(i));
  }
  return true;
}

/**
 * **对脚跟随**的落点（工单 mspm0-slot-conflict/05）：把 `roleKey` 绑到 `pin` 时，
 * 成对角色（谓词 `pair`）该被写到哪只脚。
 *
 * 返回形状（`null` = 没有对脚 / 这对此刻搬不动）：
 * - `{same: true, mate, at}`：对脚**原地不动**就成立（候选脚与对脚当前脚实例仍有交集，
 *   pwm 两通道同理）——调用方只需写本脚；
 * - `{same: false, mate, from, to, bound}`：对脚须跟到 `to`（`from = null` / `bound = false`
 *   = 对脚此刻未绑、走默认脚）。调用方与 `to` 一起写，两脚一次提交。
 *
 * 落点规则（确定、可复述）：对脚 `selectable` 里满足①**与本脚同实例**（pwm 按通道
 * 过滤后比基名；uart/i2c 按实例名精确比）②对脚**自己的其它**谓词放行（槽位互斥 /
 * 端口组照常求值——对脚跟过去也不许踩坏别的门禁）③未被别的角色占用 的脚；
 * 其中**优先「与本脚同一份实例集」的那只**（板上成对脚彼此同实例集：TX 点 PA28 时
 * 落 PA31 比落 PA0 更贴近用户意图），同级内取**板定义引脚序首个**。
 * 为什么用「对脚自身谓词」而不是完整 `pinModelVerdict`：这里正在算的就是那条成对
 * 谓词，递归调用会首尾相接（跳过它，其余谓词照常求值）。
 *
 * ⚠ 本函数**只给落点，不写回**：`bindings` 只用于读「对脚此刻在哪 / 谁占着脚」，
 * 写回由 `ui/generate-pins.js` 在同一次提交里完成（两脚一次写，中间无非法态被提交）。
 */
export function pinPairFollow(model, board, roleKey, pin, bindings) {
  if (!pin || !board || !Array.isArray(board.pins)) return null;
  const entry = pinModelEntry(model, roleKey);
  if (!entry) return null;
  const pairs = pinModelConstraints(entry).filter(isPairConstraint);
  if (pairs.length !== 1) return null;    // 无对脚 / 两条成对谓词说法不一 → 不跟
  const pair = pairs[0];
  const mateKey = pair.pair;
  const mate = pinModelEntry(model, mateKey);
  if (!mate || !Array.isArray(mate.selectable) || !mate.selectable.length) return null;
  const isPwm = entry.type === "pwm";
  const matePin = (name) => board.pins.find((p) => p && p.name === name) || null;
  // 本脚候选实例（pwm = 按本脚通道过滤后的**基名**；uart/i2c = 实例名精确集）
  const mine = isPwm
    ? pwmBases(pinInstanceTokens(pin, "pwm"), pinRoleChannel(roleKey))
    : pinInstanceTokens(pin, entry.type);
  // 对脚侧的判据 = 「对脚这只脚上的实例」与对脚集合比（pwm 用谓词里对脚未过滤
  // 实例集按对脚通道取基名）——**不是**把对脚候选塞进 `pinConstraintHolds`：
  // 那条谓词的求值方向是「本脚实例 ∈ 对脚实例集」，对脚候选在上面会被当成对脚集合。
  const mateSideBases = (foot) => (isPwm
    ? pwmBases(pinInstanceTokens(foot, "pwm"), pinRoleChannel(mate.role))
    : pinInstanceTokens(foot, mate.type));
  const mateOk = (foot) => {
    const theirs = mateSideBases(foot);
    return mine.some((i) => theirs.includes(i));
  };
  // 对脚此刻的有效脚：绑定值，缺省 = 默认脚（与后端观测口径一致）
  const mateNow = observedPin(bindings, mateKey) || mate.default;
  const mateNowPin = mateNow ? matePin(mateNow) : null;
  const occupied = new Map();
  for (const [k, v] of Object.entries(bindings || {})) occupied.set(v, k);
  const moved = observedPin(bindings, roleKey) || entry.default;
  const mateType = isPwm ? "pwm" : mate.type;
  const mineSet = instanceKey(pin, isPwm ? "pwm" : entry.type);

  // ① 对脚**原地不动**就成立（对脚当前脚与候选脚实例集仍有交集）→ 调用方只写本脚
  if (mateNowPin && mateOk(mateNowPin)) {
    return { same: true, mate: mateKey, from: mateNow, to: mateNow, bound: true };
  }

  // ② 对脚要跟：落点 = 对脚 `selectable` 里满足下面全部的脚，**优先「与本脚同一份
  //    实例集」的那只**（板上成对脚彼此同实例集：TX 点 PA28 时落 PA31 比落 PA0 更
  //    贴近用户意图），同级内取**板定义引脚序首个**。判据 = 对脚候选与谓词里的
  //    对脚实例集有交集（= 后端「两脚有效实例集交集非空」）。
  let first = null;
  for (const name of mate.selectable) {
    const candidate = matePin(name);
    if (!candidate || candidate.kind !== "io") continue;
    if (!mateOk(candidate)) continue;
    // 对脚**自己的其它**谓词照常求值（跳过正在算的成对那条，防首尾相接）：
    // 槽位互斥 / 端口组照样不许对脚踩——对脚跟过去也不能踩坏别的门禁
    const blocked = pinModelConstraints(mate).some(
      (c) => !isPairConstraint(c) && !pinConstraintHolds(c, mate, mateKey, candidate)
    );
    if (blocked) continue;
    // 空闲：占着的是别人就让位（与 `bindRole` 既有「替换占用者」语义一致），
    // 占着的若正是本次要搬的箱位（本脚自己 / 对脚原地）→ 不算冲突
    const holder = occupied.get(name);
    if (holder && holder !== mateKey && holder !== roleKey && name !== moved) continue;
    const landed = {
      same: false, mate: mateKey,
      from: observedPin(bindings, mateKey) || null,
      to: name, bound: !!observedPin(bindings, mateKey),
    };
    if (instanceKey(candidate, mateType) === mineSet) return landed;
    if (first === null) first = landed;
  }
  return first;                             // 全无落点 → null（这次点击照旧不成立）
}

/** pwm 实例集按通道过滤后取基名（与 `pinConstraintHolds` 的 pwm 分支同口径）。 */
function pwmBases(instances, channel) {
  return (instances || [])
    .filter((i) => !channel || String(i).endsWith("_" + channel))
    .map((i) => String(i).split("_")[0]);
}

/** 某脚某类型实例集的规范化键（排序去重；用于「同一份实例集」的落点偏好）。 */
function instanceKey(pin, type) {
  if (!pin || !type) return "";
  return pinInstanceTokens(pin, type).slice().sort().join("|");
}

/** 观测绑定里某角色的值（`bindings` = 用户改动的那份 `{roleKey: pinName}`）。 */
function observedPin(bindings, roleKey) {
  if (!bindings || typeof bindings !== "object") return "";
  const v = bindings[roleKey];
  return typeof v === "string" ? v : "";
}

/**
 * 某角色此刻能否绑到某脚（模型口径）。
 *
 * - 无模型 / 无该角色条目 → `true`（判据没到 = 不参与判定，绝不假拦；菜单第一层
 *   另有前端 `pinListsType` 与 `pinSelectableByType` 把住）；
 * - 非 io 脚 → `false`；
 * - 不在 `selectable` → `false`；
 * - 谓词：**全部**成立才放行（`constraints` 多条并存 = 并列门禁，任一条不成立即挡）；
 *   唯一的例外 = 成对实例那一条可以靠「对脚一起搬」满足（见 `pinPairFollow`）。
 *
 * `bindings`（可选）= 当前**观测绑定**（`{roleKey: pinName}`，即 `collectBindings` 那份）：
 * 成对跟随要据此知道对脚此刻在哪、哪些脚被别的角色占着。不给 = 只有本脚自己那份
 * 观测（旧调用口径，成对跟随只认默认）。
 */
export function pinModelVerdict(model, board, roleKey, pin, bindings) {
  if (!pin || pin.kind !== "io") return false;
  const entry = pinModelEntry(model, roleKey);
  if (!entry) return true;
  if (!Array.isArray(entry.selectable) || !entry.selectable.includes(pin.name)) {
    return false;
  }
  return pinModelFailing(model, board, roleKey, pin, bindings).length === 0;
}

/**
 * 某角色在某脚上**不成立**的谓词（`pinModelVerdict` / `pinModelMissReason` 的共用件）——
 * 「成对跟随」这一层的**唯一**落点：凡**只有**成对实例那一条不成立、且
 * `pinPairFollow` 给得出落点时，该条视为成立（同一次提交里对脚会被一起写过去，
 * 整份 bindings 因此仍合法）。其余谓词（端口组 / 槽位 / 多条并存里的其它条）
 * 一字不让：跟不过去就照旧灰显 + 原因为后端逐字文案。
 */
function pinModelFailing(model, board, roleKey, pin, bindings) {
  const entry = pinModelEntry(model, roleKey);
  if (!entry) return [];
  const failing = pinModelConstraints(entry).filter(
    (c) => !pinConstraintHolds(c, entry, roleKey, pin)
  );
  if (failing.length !== 1 || !isPairConstraint(failing[0])) return failing;
  const follow = pinPairFollow(model, board, roleKey, pin, bindings);
  return follow ? [] : failing;
}

/**
 * 谓词挡住的**原因**（后端逐字中文）；没被谓词挡住（含能力层挡的 / 无模型）→ 空串。
 *
 * 多条并存时给**第一条不成立**的（与 `pinModelVerdict` 的短路顺序一致）。
 * 能力层挡住的原因归前端既有文案（`pinMissReason` 的类型/实例提示），本函数只补
 * 「跨角色谓词」这一层的解释。成对跟随解得开的那一条不算挡住（与放行口径同源）。
 */
export function pinModelMissReason(model, board, roleKey, pin, bindings) {
  const entry = pinModelEntry(model, roleKey);
  if (!entry) return "";
  if (!pin || pin.kind !== "io") return "";
  if (!Array.isArray(entry.selectable) || !entry.selectable.includes(pin.name)) {
    return "";
  }
  const failing = pinModelFailing(model, board, roleKey, pin, bindings)[0];
  return failing ? failing.reason || "" : "";
}

/**
 * 类型级可绑判据（旧口径，**仅降级路径**用）：脚能力集里有该类型（或该类型的
 * 实例 token）。模型未到 / 拉取失败时用它兜底，行为与本工单之前一致。
 */
export function pinSelectableByType(pin, type) {
  if (!pin || pin.kind !== "io") return false;
  const prefix = type + ":";
  return ((pin.capabilities) || []).some(
    (t) => typeof t === "string" && (t === type || t.startsWith(prefix))
  );
}
