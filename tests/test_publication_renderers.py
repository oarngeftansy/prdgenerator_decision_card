from backend.accepted_publication import markdown_to_feishu_xml
from backend.publication_renderers import (
    final_document_to_annotated_markdown,
    final_document_to_feishu_xml,
    final_document_to_html,
)


def _document():
    return {
        "title": "执行策划案",
        "systems": [{
            "title": "局内成长",
            "objects": [{
                "title": "技能选择",
                "chapters": [{
                    "title": "候选生成",
                    "foldIntoObject": False,
                    "groups": [{
                        "title": "逻辑规则",
                        "sentences": [
                            {"text": "玩家升级时进入技能选择。", "publicationState": "confirmed"},
                            {"text": "系统抽取3个不同候选技能。", "publicationState": "inferred"},
                            {"text": "已满级技能移出候选池。", "publicationState": "proposed"},
                            {"text": "配置存在互斥定义。", "publicationState": "conflict"},
                        ],
                    }],
                }],
            }],
        }],
    }


def test_web_preview_uses_yellow_and_red_without_meta_labels():
    html = final_document_to_html(_document())
    assert 'class="publication-inferred"' in html
    assert 'class="publication-proposed"' in html
    assert 'class="publication-conflict"' in html
    assert "系统抽取3个不同候选技能。" in html
    assert "【推断】" not in html
    assert "待确认" not in html


def test_annotated_markdown_keeps_state_in_invisible_comments_only():
    markdown = final_document_to_annotated_markdown(_document())
    assert "<!-- PUBLICATION_STATE:inferred -->\n- 系统抽取3个不同候选技能。" in markdown
    assert "<!-- PUBLICATION_STATE:proposed -->\n- 已满级技能移出候选池。" in markdown
    assert "【推断】" not in markdown
    assert "待确认" not in markdown


def test_feishu_xml_has_native_yellow_highlight():
    xml = final_document_to_feishu_xml(_document())
    assert '<span background-color="light-yellow">系统抽取3个不同候选技能。</span>' in xml
    assert '<span background-color="light-yellow">已满级技能移出候选池。</span>' in xml
    assert 'background-color="light-red"' in xml


def test_accepted_markdown_transport_preserves_yellow_and_removes_comment():
    markdown = """# 执行策划案

<!-- PUBLICATION_STATE:proposed -->
- 已满级技能移出候选池，同次候选不重复。
"""
    rendered = markdown_to_feishu_xml(markdown)
    assert 'PUBLICATION_STATE' not in rendered.body_xml
    assert '<span background-color="light-yellow">已满级技能移出候选池，同次候选不重复。</span>' in rendered.body_xml
    assert "推断" not in rendered.body_xml
    assert "待确认" not in rendered.body_xml
