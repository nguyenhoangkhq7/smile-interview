import unicodedata

import pytest

from matching_cv.app.schemas.skill_extraction import Evidence, ExtractedSkill
from matching_cv.app.services.competency_granularity import normalize_inflectional_slug
from matching_cv.app.services.implicit_skill_postprocessor import ImplicitSkillPostprocessor
from matching_cv.app.services.skill_postprocessor import SkillPostprocessor
from matching_cv.research.data.canonical_skill_normalizer import normalize_canonical_skill


@pytest.mark.parametrize('name, expected', [
    ('Phát triển AI Coding Agent', 'phát-triển-ai-coding-agent'),
    ('Thị trường chứng khoán', 'thị-trường-chứng-khoán'),
    ('Khoa học máy tính', 'khoa-học-máy-tính'),
    ('Đồ án', 'đồ-án'),
])
def test_vietnamese_slugs_preserve_letters_and_pass_extraction_contract(name, expected):
    for form in [name, unicodedata.normalize('NFD', name)]:
        assert SkillPostprocessor.slugify_skill(form) == expected
        assert ImplicitSkillPostprocessor.slugify_skill(form) == expected
        assert normalize_inflectional_slug(form) == expected
        assert normalize_canonical_skill(form) == expected
    extracted = ExtractedSkill(skill_id=expected, surface_forms=[name],
                               evidences=[Evidence(surface_form=name, sentence=f'Yêu cầu {name}.', kind='skill')])
    assert extracted.surface_forms == [name]


def test_existing_technology_aliases_remain_distinct():
    assert normalize_canonical_skill('Node.js') == 'nodejs'
    assert normalize_canonical_skill('C++') == 'c++'
    assert normalize_canonical_skill('C#') == 'c#'
    assert normalize_canonical_skill('Java') != normalize_canonical_skill('JavaScript')
