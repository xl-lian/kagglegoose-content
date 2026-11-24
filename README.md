# KaggleGoose 内容源

[打开 KaggleGoose 网页版](https://xl-lian.github.io/kagglegoose-content/)，浏览竞赛、阅读双语讲解并记录复现进度。网页与 iOS 共用公开竞赛目录和成绩凭据。在线快照位于 [v1/catalog.json](https://xl-lian.github.io/kagglegoose-content/v1/catalog.json)。

GitHub Actions 每天按洛杉矶当地时间 00:00 和 12:00 读取公开竞赛目录、排行榜、获奖队伍链接和固定版本 Notebook。每场在得分与最近运行排序下分别查看 30 个公开候选。赛中只接受可归属至具体版本的成绩，以同分并列方式对照全榜前 10%。近期结束竞赛持续检查最终前三名的公开 writeup。无公开成绩的比赛仍可出现在竞赛目录中。

## LLM 筛选与双语讲解

在本仓库的 **Settings → Secrets and variables → Actions** 添加 `DEEPSEEK_API_KEY` 和 / 或 `OPENAI_API_KEY`。在已登录仓库管理员账号的终端也可以分别运行以下命令，按提示输入密钥。

```sh
gh secret set DEEPSEEK_API_KEY --repo xl-lian/kagglegoose-content
gh secret set OPENAI_API_KEY --repo xl-lian/kagglegoose-content
```

两项都配置时，DeepSeek 阅读已核验来源，筛选具有可复现步骤的方案；OpenAI 为入选方案撰写中英讲解和复现实验。只配一家时由该服务完成两步。默认模型分别为 `deepseek-v4-flash`、`gpt-6.2-sol`，可用同名仓库变量 `DEEPSEEK_MODEL` 和 `OPENAI_MODEL` 覆盖。两个服务各用自己的官方 HTTPS 接口。模型故障或引用验证失败时可切换另一家，每次运行最多发起 8 次模型请求，费用计入提供密钥的账号。

每步必须给出原文章节或代码单元及可在其中匹配的原文摘录。验证通过后才发布总结。原文指纹、筛选结果及采用的服务与模型随目录保存。未入选条目保留已验分索引；网络失败或当轮预算用完的条目留待后续处理。已有完整讲解继续保留，待讲解记录与已有源码导读都可进入筛选队列。

每步讲解分为做法、`why`（为什么这样做）和 `limit`（局限与注意）。`findings` 收录作者报告的实验结论，每条附对照设置、结论边界和原文位置；作者给出成组数值时附 `chart`（柱状或折线）。图中每个数值都必须在所引章节里逐字出现且符号一致，结论文字里的小数也必须能在原文中找到；图表数值对不上时只丢弃图表，结论照常发布。原文没有报告实验数值时 `findings` 为空数组。较早发布、尚无 `findings` 的讲解会在每轮预留的 3 次请求内补充细节，步骤标题和原文位置保持不变，复现进度不受影响。

配置完成可在 **Actions → Refresh and publish → Run workflow** 勾选 `editorial_only`，直接从当前目录筛选。定时任务会先采集再筛选。手机端用于个人追问的 Key 只保存在设备上。

在 Python 3.12 及安装了 curl 的环境中运行：

```sh
python3 -m unittest discover -s tests
python3 refresh.py
```


网页版位于 `site/`，可直接使用静态 HTTP 服务预览。它从同源的 `v1/catalog.json` 读取目录，收藏、笔记与复现进度写入浏览器本地存储。

<details>
<summary>BirdCLEF 首页题图</summary>

[题图文件](site/assets/birdclef.jpg) 由内置 ImageGen 生成。提示词如下。

> Wide editorial wildlife photograph for a BirdCLEF birdsong article cover. A small vivid teal-jade and cinnamon-orange tropical songbird in three-quarter profile on a slender natural twig, beak slightly open in song. Place the entire bird in the right third, near x=75%, y=48%. Left half is quiet dark pine-green out-of-focus rainforest for a headline overlay. Soft daylight on intricate feathers, gentle film grain, sophisticated natural history magazine photography. Landscape 3:2, no text, no logos, no border.

</details>
