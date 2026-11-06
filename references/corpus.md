# 案例库与运行方式

## 资料范围

`corpus.csv` 整理自官方战果人事表「艦隊名＆コメント選抜遊撃部隊群」OCR 初提：2018-07 至 2026-09，99 个作战月份，20 个服务器，1,980 张图片，15,840 条记录。来源图遵循 `https://w00g.kancolle-server.com/kcscontents/information/image/rankYYMMSS.jpg`。`SS` 是服务器编号，记录序号是栏目从上到下的位置，不是战果排名。资料截至 2026-09，不应称为实时完整库。

原数据包含 8 条完整人工核对、32 条部分字段人工核对、3,478 条双 OCR 一致但未人工核对，以及 12,322 条待校对记录；7 条舰队名未识别。双 OCR 一致和模型分数都不能视为原文正确的保证。部分 OCR 文本超过 12 字，保留以便核对，不能当作放宽限制的依据。

本技能另有 `curated-examples.json`：1000 条舰队名与 comment 已对照 148 张原图裁剪进行目视核实，覆盖 2018-07—2026-09 的全部 99 个作战月份、12 个日历月份和 20 个服务器。每例都有中文释义、主题标签和来源；其中 240 例另附较详细的写法解读和依赖说明，760 例使用简要注释（`annotation_level: brief`）。文字核实范围相同，注释深度不同；简要注释不认定引用出处或角色设定。

126 条案例修正了识别文字，`source_text` 保留原始 OCR，案例正文为核实版本；没有 `source_text` 的旧案例与原数据同文。检索对这些字段采用核实版本，出现修正时附 `ocr_text`，保持完整 CSV 原文、校对状态和来源不变。[核实来源清单](verification-manifest.json) 记录原图 URL、SHA-256、核实日期及对应案例 ID；新增批次还记录裁剪坐标。图片只能支持可见字形比对，不能单凭字形区分所有形同的 Unicode 字码。旗舰未额外逐字复核，不得由此虚构角色设定。提督名、司令部等级及旗舰等级未打包，它们不参与文案创作。

`corpus-meta.json` 记录输入文件与打包 CSV 的 SHA-256、记录数、覆盖范围、空字段和长度异常数量。数据只有入选者，不含完整候选池或未入选对照；频数与文字相似度都不是入选概率。

## 依赖与命令

本地案例检索、重建和文字校验脚本需要 Python 3.9 或以上，仅使用标准库，无需安装包、API 密钥或联网。角色资料核查使用宿主的联网工具，详见 [角色资料核查](character-research.md)。`python` 可按环境换成 `python3`、`py -3` 或解释器绝对路径。下列路径均以技能目录为基准；从其他目录调用请改成绝对路径。没有运行环境时仍可使用创作指南与核实案例，但全库检索及脚本校验不可用。

```text
python scripts/corpus.py stats
python scripts/corpus.py show 180911-03 230214-08
python scripts/corpus.py search --query "遠征 任務" --limit 8
python scripts/corpus.py search --reviewed-only --seed 42
python scripts/corpus.py search --reviewed-only --theme "双关" --limit 6
python scripts/corpus.py search --theme "食物" --expand-query "ご飯 食べ 料理 おにぎり カレー" --limit 8
python scripts/corpus.py search --query "桜" --month 3,4 --since 2024-01 --until 2026-09
python scripts/corpus.py check /absolute/path/candidates.json
```

`--query` 中的词默认按“或”匹配舰队名和 comment；`--all` 改为全部词都要出现。可用日文、中文、标点，均按普通文本处理，不是正则或命令。需查固定短语时把它作为一个无空格的查询词。`--flagship` 是原旗舰字段的子串匹配，可能受 OCR 错误影响；它不代表内容一定与该舰有关。

月份可以传 `--month 10` 或 `--month 9,10,11`，与关键词、旗舰、起止作战月份一起筛选。中文主题由智能体转成相关日语检索词；涉及角色时也可用核实后的日文名或台词关键词检索。无结果时放宽词汇或月份，不虚构匹配案例。

结果默认最多 8 条，最多允许 30 条。相同舰队名＋comment 组合经全半角及标点归一后去重，优先保留文字核实程度较高的记录；同一路结果按关键词命中数、核实程度排序，同分随机排列，`--seed` 可复现。检索不会根据获奖次数为写法加分。`--reviewed-only` 仅保留本次核实文本或原数据完整人工核对文本，不把“部分人工核对”误当整行已确认。

`--theme` 按核实案例的中文标签做子串筛选，可与日文关键词、月份和旗舰同时使用。例如 `--theme "角色"` 会包含“角色”和“角色名”等标签。只有带编辑标签的 1000 条核实案例参与主题筛选，不把未标注的其余记录视为不属于该主题；[主题索引](curated-index.md) 提供了标签列表和分组入口。

按主题拓展灵感时，同时提供 `--theme` 和 `--expand-query`：前者查询已标注案例，后者用当前情境相关的日文词独立检索全库，两路结果取并集并去重。关键词由智能体根据本次需求展开，不固定套用示例词表。普通的 `--theme ... --query ...` 仍表示交集；若两者都提供，`--query` 只进一步筛选标签这一路，扩展词独立匹配。`--all` 要求各自这一路的全部查询词都出现。月份、起止范围、旗舰和 `--reviewed-only` 同时约束两路，扩展不会绕过这些条件。

合并展示时，主题案例与扩展结果交替选取；扩展一路优先展示未标注线索，再用其他带标签的关键词命中补足。`--limit 1` 优先展示主题案例；两路有不同记录时，至少返回 2 条才能分别展示。某一路无结果时用另一路补足，不编造匹配。`--expand-query` 必须与 `--theme` 一起使用；仅按关键词搜索全库时用 `--query`。扩展只提供字面匹配线索，不为原始记录新增标签，也不改变文字核实状态。引用未经核实的历史原文前应核对来源图。

## 输出字段

`stats` 的 `retrieval_coverage` 与每次检索的 `scope` 动态统计全库数量、带标签数量、未标注数量和标签覆盖百分比；当前为 15,840、1,000、14,840 和 6.31%。检索还给出 `eligible_records`、`eligible_theme_tagged_records`、`eligible_theme_untagged_records` 和 `eligible_text_verified_records`，表示应用月份、旗舰、核实状态等公共条件后、应用主题及关键词前的范围；`scope.filters` 记录这些条件。`scope.mode` 区分全库搜索、仅标签筛选与标签加关键词扩展。主题命中数与索引频数只描述已标注子集，不代表全库主题分布。

`matched_records` 是两路合并、组合去重前的记录数；`unique_combinations` 是去重后的总数，`returned` 是受数量限制的实际展示数。`matched_by_route` 和 `returned_by_route` 分别统计各路命中及展示数，同一记录可以同时命中两路，因此分路计数之和可能超过合并计数。每条结果的 `retrieval.routes` 标明来自 `theme`、`keywords`、`all_records` 或 `keyword_expansion`，`query_matches` 和 `expansion_matches` 列出实际命中的查询词。关键词匹配依据不构成编辑主题标签；`warnings` 提示标签范围与扩展结果的使用边界。

CSV 字段为 `id,month,server_id,fleet,comment,flagship,review_status,review_notes,source_url`。唯一 `id` 形如 `260918-03`。检索返回的 `curated` 对象包含核实字段、主题和中文意思；`observation_zh`（写法解读）与 `dependency_zh`（依赖说明）为可选字段。其中中文解读是技能作者对表达的理解，不是官方解释。`source_text` 用于检查核实案例所依据的 OCR 快照是否发生变化，`ocr_text` 在返回的正文已修正时记录原文。

`check` 输入可以是单个对象或对象数组。`comment` 必填且非空；`fleet` 可不填，表示本次不生成舰队名；出现时必须是非空字符串。`flagship` 可选，仅保留为信息，不进行角色事实校验。其它键不会被当作游戏正文。

检查分别返回两栏的码点数、UTF-16 单元数、错误、提示，以及历史同文和近似记录。使用 NFKC、大小写与标点归一查重；不改变交付正文。短于 6 字的句子只做同文检查，较长句子的模糊检查只提示较高文字相似度，不识别同义改写、角色事实或日语自然度。候选数组内重复的 comment 也会提示。全部长度及字符检查通过时退出码为 0；存在不合法候选为 1；参数或文件错误为 2。通过不等于适合直接使用，还需编辑判断。

## 长度依据

[舰これ攻略 Wiki 的说明](https://wikiwiki.jp/kancolle/%E3%81%BE%E3%82%81%E3%81%A1%E3%81%97%E3%81%8D#lded65a6)记载两栏均为 12 字，全角半角均按 1 字计，并提到非 BMP 表情符号可能被清空。该来源是社区文档，核对日期为 2026-11-02。脚本对常规日文、数字及标点实行两栏各 12 字的上限，拒绝非 BMP、控制字符和不可见格式字符；组合附加符号与变体选择符给出提示。它不连接游戏客户端，也不宣称对每种 Unicode 字符的显示行为做过实测。

## 更新资料

把同字段格式的新提取 CSV 显式传给构建脚本：

```text
python scripts/build_corpus.py /absolute/path/extracted.csv --as-of 2026-11-02
```

这会重建技能自身的 `references/corpus.csv` 与 `corpus-meta.json`，保留核实案例文件。输入列名沿用原中文表头；任何重复 ID、无效月份、服务器或来源 URL 会报错。若新资料改动了核实案例所依据的原始文本（`source_text`，未提供时为案例同文），构建会报错，要求先复核并更新案例，不会静默覆盖。更新后检查 `stats` 和相关查询，再重新打包。
