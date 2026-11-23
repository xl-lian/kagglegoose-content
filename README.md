# KaggleGoose 内容源

面向 iOS 的公开竞赛目录、中文方案和成绩凭据。在线快照位于 [v1/catalog.json](https://xl-lian.github.io/kagglegoose-content/v1/catalog.json)。

GitHub Actions 每 6 小时读取公开竞赛目录、排行榜、获奖队伍链接和固定版本 Notebook。每场在得分与最近运行排序下分别查看 30 个公开候选。赛中只接受可归属至具体版本的成绩，以同分并列方式对照全榜前 10%。近期结束竞赛持续检查最终前三名的公开 writeup。无公开成绩的比赛仍可出现在竞赛目录中。

模型写作使用仓库 Secret `MODEL_API_KEY` 和变量 `MODEL_BASE_URL`、`MODEL_NAME`。配置兼容 Chat Completions 的 HTTPS 基础地址。每轮最多请求 8 次。没有模型配置时，已有讲解仍可阅读，新的 Notebook 按源码结构提供导读或进入已验分索引。

在 Python 3.12 及安装了 curl 的环境中运行：

```sh
python3 -m unittest discover -s tests
python3 refresh.py
```
