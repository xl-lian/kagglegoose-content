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
DESCRIPTIONS = {
    "验证设计": "定位数据划分的位置，核对用于拟合和评估的样本范围。",
    "特征处理": "跟随该调用的输入与输出，检查训练集与测试集使用的转换是否一致。",
    "模型实现": "从模型构造位置查看超参数，再沿调用链检查输入和训练逻辑。",
    "推理与评分": "对照预测或评分调用，确认模型输出如何变成提交值。",
}


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
    parts = [
        dict(
            title=label,
            body=f"源码在这里调用 {name}。{DESCRIPTIONS[label]}",
            reference=ref,
            source=0,
        )
        for label, _ in CALLS
        if label in evidence
        for name, ref in [evidence[label]]
    ]
    tags = [name for name, _ in evidence.values()]
    return dict(
        summary="从源码可直接定位 "
        + "、".join(tags[:3])
        + " 的调用。以下按代码位置展开；榜单成绩属于完整提交。",
        takeaway="先在列出的单元格确认输入、输出和数据划分，再用同一验证集测试一次单项修改。",
        steps=parts,
        tags=tags,
        readingMode="code",
    )
