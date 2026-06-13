#!/usr/bin/env python3
"""
演示查询脚本 - 展示各种搜索功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_engine.search import SearchEngine


def run_demo():
    print("=" * 60)
    print("  南开大学信息检索系统 - 功能演示")
    print("=" * 60)

    engine = SearchEngine()

    # 演示查询列表
    demos = [
        ("南开大学", "normal", "default", "普通关键词查询"),
        ("奖学金 申请", "multi", "default", "多关键词查询"),
        ("人工智能", "normal", "research_user", "个性化排序（科研用户）"),
        ("研究生 复试", "multi", "admission_user", "多关键词 + 招生用户画像"),
        ("南开*", "wildcard", "default", "通配符 * 查询"),
        ("202?年", "wildcard", "default", "通配符 ? 查询"),
        ("计算机", "normal", "study_user", "学习型用户偏好"),
    ]

    for query, stype, user, desc in demos:
        print(f"\n{'─' * 50}")
        print(f"【{desc}】")
        print(f"  查询: '{query}'  类型: {stype}  用户: {user}")
        try:
            results = engine.search(query, search_type=stype, user_id=user, page_size=5)
            print(f"  结果数: {results['total']}, 耗时: {results['elapsed']}s")
            for i, doc in enumerate(results.get("results", []), 1):
                print(f"  {i}. {doc['title'][:60]}")
                print(f"     来源: {doc['source_site']} | 分数: {doc.get('final_score', 0):.3f}")
        except RuntimeError as e:
            print(f"  ⚠ 索引未构建: {e}")
            break

    print(f"\n{'=' * 60}")
    print("  演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
