# kancolle-comment

为《舰队 Collection》（艦これ／舰C）玩家创作日语签名（comment）和舰队名的 Agent Skill。玩家用中文提出主题和喜好，智能体参考历史选拔案例，提供日语文案、中文释义与字数。

当前版本：**v1.4.0**。

## 能做什么

- 单独生成 comment，或生成舰队名与 comment 组合；支持保留指定舰队名和旗舰。
- 按玩家意图创作感想、日常互动、同行愿望、幽默和季节主题。
- 涉及角色设定时，用智能体已有的网页工具查询 kcwiki，区分游戏资料、社区解读与原创场景。普通签名采用玩家口吻，台词梗和角色独白按需使用。
- 检查两栏各 12 字的限制、特殊字符、历史同文及较高文字相似度。

## 安装与使用

将本仓库地址交给支持 Agent Skills 的智能体，请它安装此 Skill：

```text
请安装 https://github.com/asparagusThief/kancolle-comment 这个 Skill。
```

也可 [下载 ZIP](https://github.com/asparagusThief/kancolle-comment/archive/refs/heads/main.zip)，解压后将整个目录放入你的智能体支持的技能目录。保留 `SKILL.md`、`references/` 和 `scripts/` 的相对位置；安装和发现方式依宿主工具而定。

安装后可在 Codex 中这样调用：

```text
使用 $kancolle-comment，旗舰用加贺。
想写一些买点心、散步、等待归来的日常签名，附中文意思和字数。
```

只生成文字时可使用内附参考资料；全库检索与文字校验需要 **Python 3.9+**，仅使用标准库。角色在线核查需要智能体本身具备网页搜索和读取工具，本仓库不提供模型服务或 API 密钥。

## 案例库

- 完整库：**15,840 条**历史入选记录，范围为 **2018-07—2026-09**，99 个作战月份、20 个服务器。
- 核实库：**1000 条**舰队名与 comment 已对照 **148 张**原图裁剪进行目视核对，覆盖全部 **99 个作战月份**和 **20 个服务器**。
- 每例都有中文释义、主题标签与来源；其中 240 例另有详细的写法解读，新增 760 例使用简要注释，文字核实范围相同。
- 核实文本中有 **126 条**记录包含 OCR 修正，原始识别文本与来源链接一并保留。[核实来源清单](references/verification-manifest.json) 记录原图 SHA-256、核实日期及对应案例 ID。旗舰字段未在这轮目视核实范围内；原图也无法区分所有形同的 Unicode 字码。

完整库多数仍是未经逐字校对的 OCR 文本。核实库是便于参考的精选内容，不代表所有入选记录的题材分布。历史案例可提供灵感，无法据此计算获奖概率或保证入选。

从 [主题索引](references/curated-index.md) 选择案例，或在仓库根目录运行：

```text
python scripts/corpus.py search --reviewed-only --theme "相处场景" --limit 6
python scripts/corpus.py show 230101-04 250410-02
python scripts/corpus.py check candidates.json
```

`candidates.json` 示例：

```json
[{"fleet": "第一艦隊", "comment": "今日もよろしく"}]
```

更多字段、数据校对范围和命令见 [案例库说明](references/corpus.md)。

## 文件

| 路径 | 内容 |
| --- | --- |
| [SKILL.md](SKILL.md) | 智能体入口与创作流程 |
| [references/writing-guide.md](references/writing-guide.md) | 构思与编辑原则 |
| [references/character-research.md](references/character-research.md) | kcwiki 角色资料核查 |
| [references/curated-index.md](references/curated-index.md) | 核实案例主题索引 |
| `references/corpus.csv` | 完整历史 OCR 记录 |
| `references/curated-examples.json` | 核实文本、中文解读、原识别快照与来源 |
| `references/verification-manifest.json` | 原图哈希、核实日期与案例对应关系 |
| `scripts/` | 本地检索、文字校验与重建工具 |

## 数据来源与许可

历史记录整理自官方战果人事表「艦隊名＆コメント選抜遊撃部隊群」。每条记录保留原图 URL，例如 [官方表图片](https://w00g.kancolle-server.com/kcscontents/information/image/rank260918.jpg)。仓库不附原图、音频或游戏客户端文件，也未打包提督名、司令部等级和旗舰等级。

原创技能指令、脚本、说明和中文编辑解读采用 [MIT License](LICENSE)。历史玩家原文、游戏名称及其他第三方内容的权利归各自权利人；本仓库不为这些内容另行授予许可。中文解读是对文本的编辑理解，不能代替官方角色设定或评选规则。
