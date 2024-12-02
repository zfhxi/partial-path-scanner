from pypinyin import lazy_pinyin, Style
import unicodedata


def is_chinese(char):
    if 'CJK' in unicodedata.name(char):
        return True
    else:
        return False


def get_first_letter_from_pinyin(text):
    first_letter = lazy_pinyin(text, style=Style.FIRST_LETTER)[0]
    return first_letter.upper()


def sort_list_by_pinyin(lst):
    # sorted_lst = sorted(lst, key=lambda x: lazy_pinyin(x, style=Style.FIRST_LETTER))
    sorted_lst = sorted(lst, key=lambda x: ''.join(lazy_pinyin(x, style=Style.FIRST_LETTER)))
    return sorted_lst


def sort_list_mixedversion(lst):
    non_chinese_lst = []
    chinese_lst = []
    for x in lst:
        if is_chinese(x[0]):
            chinese_lst.append(x)
        else:
            non_chinese_lst.append(x)
    return sorted(non_chinese_lst) + sort_list_by_pinyin(chinese_lst)
