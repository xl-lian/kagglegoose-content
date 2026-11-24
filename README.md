# KaggleGoose 内容源

面向 iOS 的公开竞赛目录、中文方案和成绩凭据。在线快照位于 [v1/catalog.json](https://xl-lian.github.io/kagglegoose-content/v1/catalog.json)。

GitHub Actions 每 6 小时读取公开竞赛目录、排行榜、获奖队伍链接和固定版本 Notebook。每场在得分与最近运行排序下分别查看 30 个公开候选。赛中只接受可归属至具体版本的成绩，以同分并列方式对照全榜前 10%。近期结束竞赛持续检查最终前三名的公开 writeup。无公开成绩的比赛仍可出现在竞赛目录中。

## LLM 筛选与双语讲解

在本仓库的 **Settings → Secrets and variables → Actions** 添加 `DEEPSEEK_API_KEY` 和 / 或 `OPENAI_API_KEY`。在已登录仓库管理员账号的终端也可以分别运行以下命令，按提示输入密钥。

```sh
gh secret set DEEPSEEK_API_KEY --repo xl-lian/kagglegoose-content
gh secret set OPENAI_API_KEY --repo xl-lian/kagglegoose-content
```

两项都配置时，DeepSeek 阅读已核验来源，筛选具有可复现步骤的方案；OpenAI 为入选方案撰写中英讲解和复现实验。只配一家时由该服务完成两步。默认模型分别为 `deepseek-v4-flash`、`gpt-4.1-mini`，可用同名仓库变量 `DEEPSEEK_MODEL` 和 `OPENAI_MODEL` 覆盖。两个服务各用自己的官方 HTTPS 接口。模型故障或引用验证失败时可切换另一家，每次运行最多发起 8 次模型请求，费用计入提供密钥的账号。

每步必须给出原文章节或代码单元及可在其中匹配的原文摘录。验证通过后才发布总结。原文指纹、筛选结果及采用的服务与模型随目录保存。未入选条目保留已验分索引；网络失败或当轮预算用完的条目留待后续处理。已有完整讲解继续保留，待讲解记录与已有源码导读都可进入筛选队列。

配置完成可在 **Actions → Refresh and publish → Run workflow** 勾选 `editorial_only`，直接从当前目录筛选。默认定时任务每六小时采集并筛选。手机端用于个人追问的 Key 只保存在设备上。

在 Python 3.12 及安装了 curl 的环境中运行：

```sh
python3 -m unittest discover -s tests
python3 refresh.py
```
