# 记忆架构开源 —— 交付盘点（2026-11-01 18:2x）

> 口径铁律：本文件所有数字均为**当日实跑**。凡出现「结构合规」必引 `amg check`，
> 凡出现「证据可验证」必引 `amg verify-evidence`，两者同时给。**不混用一个「✓」。**

---

## 0. 一句话

**功能面已经可交付**：v0.38.5 已发布（非 draft）、CI 双绿、546 个单元测试通过、
23 个 CLI 子命令与 MCP 8 工具都在跑。
**「已知缺陷清零」还没有**：剩 3 个真代码缺陷（全在检索层），其中 1 个是正确性问题。
**「外部用户冷启动」无法自证**：需要一个真实的外部使用者，这不是我们排期能决定的。

按三种交付判据分开答：

| 交付判据 | 状态 | 还差多少 |
|---|---|---|
| A. 功能完整、可安装可运行 | **已达成** | 0；只剩把版本号自洽这一处修完发版（今天） |
| B. 已知缺陷全部关闭 | 未达成 | 今天 3–4 小时 + 约 1 天（检索层 3 个） |
| C. 外部用户冷启动验证 | 未达成 | 不由我们决定，需真实外部用户 |

---

## 1. 已完成（每条都有实测来源）

### 1.1 发布与 CI

| 版本 | commit | CI |
|---|---|---|
| v0.38.0 | `10c4850` | success |
| v0.38.1 | `5bb5eec` | success |
| v0.38.2 | `8d38ea1` | **failure**（CRLF 复发） |
| v0.38.3 | `3d8b048` | success（修在唯一入口 `write_fixture`） |
| v0.38.4 | `f3ad6c8` | success（12 job，含 4 个 Windows） |
| v0.38.5 | `41a9413` | success（41288542008 / 41288539428） |

v0.38.5 发布物实算 digest：
- `agent_memory_graph-0.38.5.tar.gz` 957,942 B → `sha256:d582b6fe…d90d`
- `agent_memory_graph-0.38.5-py3-none-any.whl` 85,673 B → `sha256:c44ba4e8…fac5`

### 1.2 能力面（23 个 CLI 子命令）

```
写入   init add import status supersede link related
读侧   search digest audit check verify verify-evidence fingerprint handoff
运维   export doctor migrate adopt expire archive
接口   mcp version
```

- **写入门禁**：`done` 无证据拒写；`path:` 证据必须 sha 实算一致；`source` 为
  `unknown`/`manual` 拒写（本轮实测：`memctl add --source manual` → `E_NO_SOURCE`）
- **只读诊断**：`audit --verify` 三桶（`evidence_absent` / `evidence_unverifiable` / `known`），
  `--root` 与 `--force-root` 显式声明证据根
- **MCP**：8 工具、每请求重开 `Memory`（`serve(..., reopen=)`）+ `check_shape` 形状校验
- **归档**：`archive` 五段证明，证明失败回滚
- **迁移**：`adopt` 只把 `unverifiable` 转 `legacy_evidence`，`missing`/`mismatch` 作为
  「关于真实引用的发现」保留（Glm仔 攻击后修正的口径）
- **基线**：`check --baseline/--write-baseline/--prune-baseline`，只减不增，
  文档级错误永不可豁免

### 1.3 健康数字（两个口径，同一份图 rev 1223）

```
amg check            835 errors
amg check --strict  1022 errors
  └ 带基线          1017 条已登记 / 548 节点；仍剩 5 条文档级（schema mismatch + 4 duplicate edge）
amg verify-evidence  checked 718 → ok 23 / mismatch 5 / missing 3 / unverifiable 687
单元测试              546 OK (skipped=1)
群图                  585 节点 / rev 1223 / memctl verify new_corruption 0
```

**这组数字的含义**：真正有字节可验的证据只有 23 + 5 + 3 = **31 条**；
687 条是 `cmd:`/`url:` 这类**没有字节可观察**的证据 —— 它们**不是通过，是「不是不通过」**。

### 1.4 当日修掉的缺陷（含我自己捅的）

| 缺陷 | 性质 |
|---|---|
| `adopt` 把对象形式 `cmd:`/`url:` 当合法证据保留 | 声称比验证器严，实际更松 |
| `adopt` 证据根写死 `cwd`，违反决策 #56 | Glm仔 攻击发现，Hermes 改两次才对 |
| `status` 遇裸串崩溃 | 已修 |
| `Memory.evidence_root` 类属性泄漏，单跑绿整套红 | 已修 |
| CRLF fixture 复发（v0.38.2 红） | 修在唯一写入入口 |
| manifest 重排 1,063 行只为加 11 行 | 想 force push 被**分支保护拒绝**，改留说明性 commit |
| **`__version__` 仍是 0.36.1，而 pyproject 是 0.38.5** | **本轮发现并修**：装 0.38.5 跑 `amg version` 自称 0.36.1；已加 `test_version_consistency.py`（变异验证：改错即红） |

---

## 2. 未完成（逐条，标注性质与能否自行解决）

### 2.1 真代码缺陷 — 检索层（这是唯一阻挡「缺陷清零」的部分）

| # | issue | 现象（实测） | 性质 |
|---|---|---|---|
| 1 | `issue.mem-arch-anchor-key-hides-unanchored` | 锚定优先键使**无锚正确答案不可达**：有锚 100% vs 无锚 **0%** | **正确性 bug，P1** |
| 2 | `issue.mem-arch-anchor-trap-adopt-asymmetry` | 同一张图 adopt 前后行为相反，裸 `group-kg/v1` 直读被锚定主键压死 | 正确性，团队自用形态 |
| 3 | `issue.mem-arch-tie-break-surface` | top-k 边界并列由**节点 id 字母序**决定名次，±1 条摆动不可归因 | 评测可复现性 |

### 2.2 口径与外部依赖

| # | issue | 说明 |
|---|---|---|
| 4 | `issue.mem-arch-recall-metric-not-hitrate` | recall@5 是**覆盖率**不是命中率，`0.692 ≠ 18/26`，对外文档措辞必须改 |
| 5 | `issue.mem-arch-cold-start-unverified` | 无真实外部用户冷启动证据。**外部依赖，不能自证** |

### 2.3 测试基建

| # | issue | 说明 |
|---|---|---|
| 6 | `issue.mem-arch-test-import-order-leak` | `sys.path` 绑到 `/tmp/amg-v341` 旧克隆，导致 `AttributeError`；换机即红 |

### 2.4 数据债（设计选择：登记不修）

- **543 / 558 节点带病**（rev 1221 普查快照；健康 2.7%）——不是 543 个 bug，
  是 543 个「历史写入没有证据」的节点
- **239 条可迁入 `legacy_evidence`**（rev 1219 快照：散文 141 + `cmd:`/`url:` 88 + missing 10）
  ——`adopt --dry-run` 已验接受且不写文件，**尚未落盘**
- `issue.mem-arch-kg-data-rev-gap-1117` ——本群 kg 历史数据缺 rev 1117

### 2.5 流程债（不是代码，是我的管理账）

- `issue.mem-arch-mini-zero-output-v036` / `mini-channel-unverified` —— Mini仔 通道未验证，
  已摘牌改由 Hermes 兼实现
- `issue.mem-arch-glm-cutover-attack-unpaid` —— Glm仔 两轮未交「一次性切换/回滚」攻击
- **本轮新发现**：`task.mem-arch-audit-verify-three-buckets`、`task.mem-arch-f-readonly-implementation`
  在图里还是 `in_progress`，但代码实测**已实现**（`audit.py:346` 三桶、`mcp.py` `reopen`+`check_shape`）
  —— 图谱状态滞后于代码，属记账债

---

## 3. 还需要多久

| 判据 | 剩余工作 | 预估 |
|---|---|---|
| **A 功能可运行** | 版本号修完跑 CI + 发 v0.38.6 | **今天，约 40 分钟** |
| **B1 记账/口径清完** | recall 措辞、3 个 task 状态回填、测试 import leak | **今天，约 2 小时** |
| **B2 239 条迁移落盘** | 需 ≥2 名成员独立结论（铁律 0）后执行 + 复查 | **今天，约 2 小时**（复核耗时为主） |
| **B3 检索层 3 个真缺陷** | 每个都要 ≥2 成员方案 + 改代码 + 评测复跑 | **约 1 天** |
| **C 冷启动** | 需真实外部用户 | **不可估** |

**合起来说**：功能可交付 = **今天**；缺陷清零 = **约 1.5 天**；冷启动 = **等外部**。

---

## 4. 不会做的事（已裁定，避免反复讨论）

- **不给裸串批量回填 sha**：`captured_at` 判据只要求非空字符串，回填后读侧同样报
  `verified`，与真采集**不可逆同形**（Jev 概率 0.94）
- **不做 `amend` 修证据**：裸串没有原始 sha，amend 只能写当前 sha，文件一改就伪装成「一直对得上」
- **不做 `evidence_legacy` 字段**：输入是图里可自填字段，比 pin 更弱
- **不把 `check` 变绿当目标**：`check` 只验形状，`protocol.check` 从不调用 `verify_evidence`
  （决策 #58）
- **不删旧节点**：只能 supersede，旧节点记为已知债务；表述禁止说「已修复」（铁律 11）

---

## 5. 对外口径（写进 README 时必须照此）

**可以写**：append-only、写入门禁、证据可追溯锚点、六态标注、TTL/归档、23 命令、MCP 8 工具、
546 测试、双平台 CI。

**必须写「未达/未验证」**：N2 检索 0.538（目标 0.70 未达）、top-5 边界由节点 id 决定、
零外部冷启动证据、realtext 只是同域回归集、`unverifiable` 类证据（687 条）不构成通过。

**不得写**：「完整可交付」「所有已知问题已解决」。

---

## 附：本盘点的图谱节点记录

群图里的节点是唯一权威记录（`knowledge-graph/graphs/记忆架构开源.json`）。
为了让项目资料夹里也有这份记录本身而不只是一个指针，节点快照同时导出到本仓库：

- [`docs/DELIVERY-STATUS-NODE-20261101.json`](DELIVERY-STATUS-NODE-20261101.json)

| 节点 id | 状态 | 说明 |
|---|---|---|
| `artifact.mem-arch-delivery-status-20261101` | superseded | 文档原先放在仓库外，证据指向旧路径，已作废 |
| `artifact.mem-arch-delivery-status-20261101-v2` | done | 文档移入 `docs/` 后的现行节点 |
