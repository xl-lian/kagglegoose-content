"""Extract traceable reading notes from executed-language syntax, without running code."""

import ast
import re

# Names map to the role of the call, not claims about its measured benefit.
CALLS = [
    (
        "验证设计",
        [
            "StratifiedGroupKFold",
            "GroupKFold",
            "StratifiedKFold",
            "TimeSeriesSplit",
            "train_test_split",
            "KFold",
        ],
    ),
    (
        "特征处理",
        [
            "TfidfVectorizer",
            "CountVectorizer",
            "OneHotEncoder",
            "StandardScaler",
            "OrdinalEncoder",
            "PCA",
            "get_dummies",
        ],
    ),
    (
        "模型实现",
        [
            "CatBoostClassifier",
            "CatBoostRegressor",
            "LGBMClassifier",
            "LGBMRegressor",
            "XGBClassifier",
            "XGBRegressor",
            "RandomForestClassifier",
            "RandomForestRegressor",
            "LogisticRegression",
            "Ridge",
            "MLPClassifier",
            "Sequential",
            "AutoModelForSequenceClassification",
            "AutoTokenizer",
            "Conv2d",
            "Conv2D",
        ],
    ),
    (
        "推理与评分",
        [
            "roc_auc_score",
            "mean_squared_error",
            "predict_proba",
            "softmax",
            "rankdata",
            "log_loss",
        ],
    ),
]
# Teaching notes describe a reproducible check for an observed call. They do
# not attribute settings, training decisions or score gains to the author.
CHECKS = [
    (
        ("GroupKFold", "StratifiedGroupKFold"),
        "打印每折的分组标识，验证训练与留出样本没有共享组，再比较各折样本量和类别比例。",
        "Print the group IDs in each fold. Check that no group occurs on both sides, then compare fold sizes and class balance.",
    ),
    (
        ("StratifiedKFold",),
        "逐折统计标签比例与少数类样本数。比例相近仍可能存在同一对象跨折的问题，另行检查重复记录。",
        "Count labels and minority examples in every fold. Similar proportions can still conceal the same entity on both sides, so check for duplicates separately.",
    ),
    (
        ("TimeSeriesSplit",),
        "画出每折的训练终点与验证起点，逐项检查滞后或滚动统计只使用当时已知的值。",
        "Plot each training cutoff and validation start. Verify that lags and rolling statistics use only values available at that point.",
    ),
    (
        ("KFold", "train_test_split"),
        "保存训练与验证样本索引，检查重复对象和目标分布。复现时沿用这些索引，这样分数变化才便于归因。",
        "Save the training and validation indices, inspect duplicate entities and compare target distributions. Reuse those indices to isolate the effect of the next change.",
    ),
    (
        ("OneHotEncoder", "get_dummies", "OrdinalEncoder"),
        "选一个只在验证集中出现的类别，跟踪它经过编码后的值与列位置。检查两侧的列是否对齐，以及未知类别如何处理。",
        "Trace a category seen only in validation through the encoder. Check its output value, column alignment and how unseen categories are handled.",
    ),
    (
        ("TfidfVectorizer", "CountVectorizer"),
        "选两个相似文本比较词向量，检查词表在哪些样本上拟合，以及验证集中的新词如何处理。",
        "Compare vectors for two similar texts. Trace which documents fit the vocabulary and what happens to words seen only in validation.",
    ),
    (
        ("StandardScaler", "PCA"),
        "记录训练折拟合的参数，使用同一组参数变换验证折。检查变换后数值范围或保留维数，再比较验证误差。",
        "Record the transformation fitted on training data and reuse it on validation. Inspect the resulting scale or dimension before comparing holdout error.",
    ),
    (
        ("predict_proba", "softmax", "log_loss"),
        "跟踪一行输出，核对类别顺序与提交列。观察高置信错误和低置信正确样本，检查概率是否需要校准。",
        "Trace one output row and align class order with submission columns. Inspect confidently wrong examples and weakly correct ones when evaluating calibration.",
    ),
    (
        ("roc_auc_score", "rankdata"),
        "取一对正负样本，比较它们的排序如何影响指标。核对传入的是连续分数还是离散标签，并按同一验证集比较。",
        "Inspect a positive–negative pair and its ordering. Check whether the metric receives continuous scores or hard labels and compare on the same holdout.",
    ),
    (
        ("mean_squared_error",),
        "保存每行残差并排序，查看少数大误差对平方误差的贡献。确认计算时使用的是原目标还是变换后的目标。",
        "Sort the residuals and inspect how much large misses contribute to squared error. Check whether evaluation uses the original or a transformed target.",
    ),
    (
        (
            "CatBoostClassifier",
            "CatBoostRegressor",
            "LGBMClassifier",
            "LGBMRegressor",
            "XGBClassifier",
            "XGBRegressor",
            "RandomForestClassifier",
            "RandomForestRegressor",
        ),
        "记录树的数量、控制复杂度的参数与输入列。在同一验证折只改变一个参数，同时观察训练误差和验证误差是否出现分化。",
        "Record the tree count, complexity controls and input columns. Change one setting on a fixed fold and compare training and validation error for signs of overfitting.",
    ),
    (
        ("LogisticRegression", "Ridge"),
        "查看正则化强度与输入尺度。在相同划分上对比两组强度，检查系数大小与验证误差是否同步变化。",
        "Inspect regularization strength and feature scale. Compare two strengths on a fixed split and see how coefficient magnitudes and validation error change.",
    ),
]
DEFAULT_CHECK = (
    "跟踪一个批次的输入、输出形状和目标标签，固定验证集跑一次基线，再单独改变一项设置。",
    "Trace input shapes, output shapes and target labels for one batch. Run a baseline on a fixed holdout and change one setting at a time.",
)


def code_notes(evidence):
    parts = []
    for label, _ in CALLS:
        if label not in evidence:
            continue
        name, ref = evidence[label]
        zh, en = next(
            ((zh, en) for names, zh, en in CHECKS if name in names), DEFAULT_CHECK
        )
        parts.append(
            dict(
                title=label,
                body=f"源码在这里调用 {name}。阅读时可以这样核查：{zh}",
                bodyEN=f"The source calls {name} here. Reading exercise: {en}",
                reference=ref,
                source=0,
            )
        )
    tags = [name for name, _ in evidence.values()]
    return dict(
        summary="从源码可直接定位 "
        + "、".join(tags[:3])
        + " 的调用。下面按原始单元格跟踪数据、模型或评分过程，榜单成绩属于完整提交。",
        summaryEN="The source contains calls to "
        + ", ".join(tags[:3])
        + ". Follow the cited cells to trace the pipeline. The leaderboard score belongs to the complete submission.",
        takeaway="先在列出的单元格确认输入、输出和数据划分，再用同一验证集测试一次单项修改。",
        takeawayEN="Trace inputs, outputs and data splits in the cited cells, then change one item on the same validation set.",
        tags=tags,
        steps=parts,
        readingMode="code",
    )


def guide(material):
    chunks = re.split(r"(?m)^Cell (\d+):\n", material)
    cells = list(zip(chunks[1::2], chunks[2::2])) or [("", material)]
    evidence = {}
    for number, code in cells:
        # Strip notebook magics before parsing; prose and non-Python cells can be skipped.
        lines = [
            line
            for line in code.splitlines()
            if not line.lstrip().startswith(("%", "!"))
        ]
        try:
            tree = ast.parse("\n".join(lines))
        except (SyntaxError, ValueError, RecursionError):
            continue
        names = {
            getattr(node.func, "attr", getattr(node.func, "id", ""))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        for label, candidates in CALLS:
            for name in candidates:
                if name in names and label not in evidence:
                    ref = "Cell " + number if number else "Source file"
                    evidence[label] = (name, ref)
    if len(evidence) < 2:
        return None
    return code_notes(evidence)
