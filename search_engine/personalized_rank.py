"""
个性化排序模块

通过用户画像对搜索结果进行规则重排。
不同用户画像对文档的类别/关键词有不同的偏好权重。
"""

# 用户画像定义
USER_PROFILES = {
    "default": {
        "name": "默认用户",
        "description": "按相关性排序，无特殊偏好",
        "weights": {},
        "source_weights": {},
    },
    "study_user": {
        "name": "学习型用户",
        "description": "偏好教务、课程、考试、奖学金、本科生教学",
        "weights": {
            "教务": 2.0,
            "课程": 1.8,
            "考试": 1.8,
            "奖学金": 1.6,
            "本科生教学": 1.6,
            "学生工作": 1.4,
            "教学": 1.4,
            "选课": 1.4,
            "成绩": 1.3,
            "培养": 1.2,
            "本科": 1.3,
            "学籍": 1.3,
            "毕业": 1.3,
            "学位": 1.3,
        },
        "source_weights": {
            "南开大学教务部": 2.0,
            "计算机学院": 1.3,
        },
    },
    "research_user": {
        "name": "科研型用户",
        "description": "偏好科研、项目、实验室、论文、学术新闻",
        "weights": {
            "科研": 2.0,
            "项目": 1.8,
            "实验室": 1.8,
            "论文": 1.6,
            "学术": 1.5,
            "科学研究": 1.5,
            "研究": 1.5,
            "创新": 1.3,
            "基金": 1.3,
            "课题": 1.4,
            "成果": 1.3,
            "技术": 1.2,
            "学科": 1.3,
            "导师": 1.2,
            "博士后": 1.2,
            "博士": 1.3,
            "硕士": 1.2,
            "研究生培养": 1.4,
        },
        "source_weights": {
            "计算机学院": 1.4,
            "人工智能学院": 1.4,
        },
    },
    "admission_user": {
        "name": "招生型用户",
        "description": "偏好招生、研究生招生、推免、复试、调剂",
        "weights": {
            "招生": 2.0,
            "研究生招生": 2.0,
            "推免": 1.8,
            "复试": 1.8,
            "调剂": 1.6,
            "博士招生": 1.5,
            "硕士": 1.4,
            "录取": 1.5,
            "报名": 1.3,
            "考试": 1.3,
            "面试": 1.3,
            "夏令营": 1.4,
            "申请": 1.2,
        },
        "source_weights": {
            "南开大学研究生招生网": 2.0,
            "计算机学院": 1.3,
            "人工智能学院": 1.3,
        },
    },
    "news_user": {
        "name": "新闻型用户",
        "description": "偏好新闻、活动、学校动态",
        "weights": {
            "新闻": 2.0,
            "南开要闻": 1.8,
            "综合新闻": 1.6,
            "媒体南开": 1.5,
            "活动": 1.4,
            "动态": 1.3,
            "通知": 1.2,
            "公告": 1.2,
            "报道": 1.3,
            "校园": 1.2,
            "讲座": 1.2,
            "会议": 1.1,
        },
        "source_weights": {
            "南开新闻网": 2.0,
            "南开大学主站": 1.5,
        },
    },
}


class PersonalizedRanker:
    """个性化排序器"""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.profile = USER_PROFILES.get(user_id, USER_PROFILES["default"])

    def set_user(self, user_id: str):
        """切换用户画像"""
        self.user_id = user_id
        self.profile = USER_PROFILES.get(user_id, USER_PROFILES["default"])

    def compute_boost(self, doc: dict) -> float:
        """
        计算文档的个性化加成
        根据文档标题、内容、来源与用户画像的匹配程度计算 boost 值
        """
        profile_weights = self.profile.get("weights", {})
        source_weights = self.profile.get("source_weights", {})

        if not profile_weights and not source_weights:
            return 0.0

        boost = 0.0
        title = doc.get("title", "")
        content = doc.get("content", "")
        source = doc.get("source_site", "")
        text = title + " " + (content[:500] if content else "")

        # 关键词匹配加权
        for keyword, weight in profile_weights.items():
            if keyword in text:
                boost += weight

        # 来源加权
        for source_name, weight in source_weights.items():
            if source_name in source:
                boost += weight

        return boost

    def rerank(self, results: list[dict]) -> list[dict]:
        """
        对搜索结果进行个性化重排
        返回重排后的结果列表，每个结果增加 personalization_score
        """
        for doc in results:
            base_score = doc.get("score", 0.0)
            boost = self.compute_boost(doc)
            doc["personalization_score"] = round(boost, 3)
            doc["final_score"] = round(base_score + boost, 3)

        # 按 final_score 降序排列
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return results

    @staticmethod
    def get_profile_names() -> list[dict]:
        """获取所有用户画像信息"""
        return [
            {
                "id": uid,
                "name": profile["name"],
                "description": profile["description"],
            }
            for uid, profile in USER_PROFILES.items()
        ]
