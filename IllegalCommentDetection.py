# encoding: utf-8
__author__ = 'huanghongyi'
__date__ = '2020.05.05'
import ahocorasick
from pypinyin import pinyin, lazy_pinyin, Style
import pickle
import re

class IllegalCommentDetection():
    def __init__(self):
        """
        IllegalCommentDetection类初始化
        """
        self.chaizi_dict = {}
        self.fanjian_dict = {}
        self.bihua_dict = {}
        self.hanzi_list = []
        self.similarity_threshold = 0.6
        self.build_chaizi_dict('chaizi')
        self.build_fanjian_dict('chaizi/fanjian_suoyin.txt')
        self.build_stroke_num('bihua.txt')
        self.hanzi_list = list((set(self.hanzi_list).intersection(set(list(self.chaizi_dict)))).intersection(set(list(self.bihua_dict))))
        self.similarity_dict = self.load_obj('similarity')
        self.pinyin_ac = self.build_pinyin_Ac('pinyin.txt')
        self.alphabet_set = self.read_alphabet('pinyin.txt')
        self.illegal_words_list = self.read_invalid_words('色情词库.txt')
        self.illegal_words_ac = self.build_all_permutation_Ac()

    def read_chaizi_dict(self,path):
        """
        读取拆字词典

        :param path: 拆字文本路径
        :return:
        """
        with open(path,"r") as f:
            for line in f.readlines():
                line = line.strip()
                lineList = line.split(' ')
                self.chaizi_dict[lineList[0]] = lineList[0:]

    def build_chaizi_dict(self,path):
        """
        构建拆字字典，在初始化时调用

        :param:
        :return:
        """
        self.read_chaizi_dict('%s/chaizi-ft.txt'%(path))
        self.read_chaizi_dict('%s/chaizi-jt.txt'%(path))

    def build_fanjian_dict(self,path):
        """
        构建繁体字和简体字相互映射字典

        :param path: 繁体字简体字对应文本
        :return:
        """
        with open(path, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                lineList = line.split('\t')
                fan = lineList[0]
                jian = lineList[1]
                if fan != jian:
                    self.fanjian_dict[fan] = jian
                    self.fanjian_dict[jian] = fan
    def pinyin_permutation(self,text):
        """
        将所有可能的拼音组合以及原字符串返回

        :param text: 提供词组，编码为unicode
        :return: 返回所有可能拼音和汉字组合的排列
        """
        permutations = ['']
        pinyin_fl = [i[0] for i in pinyin(text, style=Style.FIRST_LETTER)]
        pinyin_lazy = lazy_pinyin(text)
        pinyin_full = [i[0] for i in pinyin(text)]
        textList = []
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff':
                textList.append(ch)
            else:
                if len(textList) <= 0 or '\u4e00' <= textList[-1][-1] <= '\u9fff':
                    textList.append(ch)
                else:
                    textList[-1] = textList[-1] + ch
        if textList[-1] == '':
            textList = textList[:-1]
        for i in range(len(pinyin_fl)):
            length = len(permutations)
            for j in range(length):
                origin = permutations[j]
                permutations[j] = origin + pinyin_fl[i]
                permutations.append(origin + pinyin_lazy[i])
                permutations.append(origin + pinyin_full[i])
                permutations.append(origin + textList[i])
        permutations = list(set(permutations))
        return permutations

    def chaizi_permutation(self,text):
        """
        将所有可能的拆字组合以及原字符串返回

        :param text: 提供词组，编码为unicode
        :return: 返回所有可能拆字组合的排列
        """
        chaizis = []
        permutations = ['']
        for ch in text:
            chaizi = []
            if ch in self.chaizi_dict:
                chaizi.extend(self.chaizi_dict[ch])
            if ch in self.fanjian_dict:
                fan = self.fanjian_dict[ch]
                chaizi.extend(fan)
                if fan in self.chaizi_dict:
                    chaizi.extend(self.chaizi_dict[fan])
            chaizis.append(chaizi)
        for chaizi in chaizis:
            length = len(permutations)
            for i in range(length):
                origin = permutations[i]
                count = 0
                for cz in chaizi:
                    if count == 0:
                        permutations[i] = origin + cz
                        count += 1
                    else:
                        permutations.append(origin + cz)
        return permutations

    def build_stroke_num(self,path):
        """
        构建汉字笔划数映射

        :param path: 笔画数文本路径
        :return:
        """
        with open(path, 'r') as f:
            for line in f.readlines():
                self.hanzi_list.append(line[0])
                self.bihua_dict[line[0]] = len(line.split(','))

    def delete_wrong_bihua_and_sort(self,chaizi):
        """
        中间函数，为了找出形似汉字，但是拆字中一些边旁改写导致笔划变化需要去除，并对拆字组排序

        :param chaizi: 一个汉字的拆字可能组合
        :return chaizi_copy: 修改后拆字组合
        """
        bihua = self.bihua_dict[chaizi[0]]
        chaizi_copy = [chaizi[0]]
        for cz in chaizi[1:]:
            bihua_count = 0
            try:
                for ch in cz:
                    bihua_count = bihua_count + self.bihua_dict[ch]
                if bihua_count == bihua:
                    chaizi_copy.append(cz)
            except Exception as e:
                pass
                #print(e)
        chaizi_copy = ["".join((lambda x: (x.sort(), x)[1])(list(i))) for i in chaizi_copy if len(i.strip()) > 0]
        return chaizi_copy

    def compare_bihua(self,character1, character2):
        """
        比较两汉字相似度

        :param character1: 汉字1
        :param character2: 汉字2
        :return : 打分
        """
        chaizi1s = self.delete_wrong_bihua_and_sort(self.chaizi_dict[character1])
        chaizi2s = self.delete_wrong_bihua_and_sort(self.chaizi_dict[character2])
        max_similarity = 0
        for chaizi1 in chaizi1s:
            bihua1_dict = {}
            for ch1 in chaizi1:
                if ch1 not in bihua1_dict:
                    bihua1_dict[ch1] = 1
                else:
                    bihua1_dict[ch1] = bihua1_dict[ch1] + 1
            for chaizi2 in chaizi2s:
                similarity = 0
                bihua1_dict_copy = bihua1_dict.copy()
                for ch2 in chaizi2:
                    if ch2 in bihua1_dict_copy and bihua1_dict_copy[ch2] != 0:
                        try:
                            similarity = similarity + self.bihua_dict[ch2]
                        except:
                            similarity = similarity + 1
                        bihua1_dict_copy[ch2] = bihua1_dict_copy[ch2] - 1
                if similarity > max_similarity:
                    max_similarity = similarity
        return min((max_similarity) / (max(self.bihua_dict[character1], self.bihua_dict[character2])), 1)

    def build_similarity_dict(self):
        """
        构建形状相似字的对应表以及打分

        :param :
        :return :
        """
        length = len(self.hanzi_list)
        for i in range(length):
            # print(hanzi_list[i])
            for j in range(i + 1, length):
                similarity = self.compare_bihua(self.hanzi_list[i], self.hanzi_list[j])
                if similarity >= self.similarity_threshold:
                    if self.hanzi_list[i] in self.similarity_dict:
                        self.similarity_dict[self.hanzi_list[i]].append((self.hanzi_list[j], similarity))
                    else:
                        self.similarity_dict[self.hanzi_list[i]] = [(self.hanzi_list[j], similarity)]
                    if self.hanzi_list[j] in self.similarity_dict:
                        self.similarity_dict[self.hanzi_list[j]].append((self.hanzi_list[i], similarity))
                    else:
                        self.similarity_dict[self.hanzi_list[j]] = [(self.hanzi_list[i], similarity)]
    #存储对象
    def save_obj(self,obj, name):
        with open(name + '.pkl', 'wb') as f:
            pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    #导出对象
    def load_obj(self,name):
        with open(name + '.pkl', 'rb') as f:
            return pickle.load(f)

    def similarity_permutation(self,text):
        """
        给出形近字替代后的排列

        :param text: 原词
        :return permutation: 用形近词替换后的词排列
        """
        permutation = [text]
        text_list = list(text)
        length = len(text_list)
        for i in range(length):
            ch = text_list[i]
            if ch in self.similarity_dict and len(self.similarity_dict[ch]) > 0:
                text_list_copy = text_list.copy();
                for sub in self.similarity_dict[ch]:
                    text_list_copy[i] = sub[0]
                    permutation.append(''.join(text_list_copy))
        return permutation

    def build_pinyin_Ac(self,path):
        """
        给出所有合法拼音出去少量单音无音调的拼音,并构建AC自动机用于匹配

        :param path: 拼音文件路径
        :return Ac: AC自动机
        """
        with open(path, 'r') as f:
            pinyin_list = [ch.strip() for ch in f.readlines()]
        Ac = ahocorasick.Automaton()
        for idx, key in enumerate(pinyin_list):
            Ac.add_word(key, (idx, key))
        Ac.make_automaton()
        return Ac

    def read_alphabet(self,path):
        """
        获取拼音相关单字符

        :param path: 拼音文件路径
        :return alphabet_set: 所有单字符set
        """
        alphabet_set = set()
        with open(path, 'r') as f:
            pinyin_list = [ch.strip() for ch in f.readlines()]
        for pinyin in pinyin_list:
            for ch in pinyin:
                alphabet_set.add(ch)
        return alphabet_set

    def replace_special_character(self,text):
        """
        替换多种unicode空格,比如 u'\u3000',u'\u0020',u'\u00A0'

        :param text: 用户的发帖内容，string
        :return: 返回一个字符串
        """
        return text.replace(u'\u3000', u'').replace(u'\u0020', u'').replace(u'\u00A0', u'')

    def remove_punctation(self,message):
        """
        删除文本中的标点

        :param message: str类型
        :return: 返回一个str类型的字符串，已删除标点符号
        """
        msg_withuot_punctation = re.sub("[\+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）]+", "", message)
        # msg_withuot_punctation = re.sub("[\s+\.\!\/_,$%^*(+\"\']+|[+——、~@#￥%……&*（）]+", "", message)
        punctation_list = list(set("[\+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）]+"))

        punctation_list.append(' ')

        return msg_withuot_punctation

    def remove_invalid_alphabet(self,message):
        """
        去除无效字母

        :param message: 原评论
        :return message: 删除无效字母后评论
        """
        pinyin_index = []
        for end_index, (insert_order, original_value) in self.pinyin_ac.iter(message):
            start_index = end_index - len(original_value) + 1
            pinyin_index.extend(list(range(start_index, end_index + 1)))
        pinyin_index = set(pinyin_index)
        message_list = list(message)
        for i in range(len(message)):
            if message_list[i] in self.alphabet_set and i not in pinyin_index:
                message_list[i] = 0
        message = ''.join([ch for ch in message_list if ch != 0])
        return message

    def read_invalid_words(self,path):
        """
        读取非法词汇

        :param path: 非法词汇文本路径
        :return illegal_words_list: 非法词汇列表
        """
        with open(path,'r') as f:
            illegal_words_list = [w.strip() for w in f.readlines()]
        return illegal_words_list

    def build_all_permutation_Ac(self):
        """
        构造非法词汇ac自动机

        :param :
        :return Ac: 非法词汇扩展Ac自动机
        """
        Ac = ahocorasick.Automaton()
        for word in self.illegal_words_list:
            sp = self.similarity_permutation(word)
            pp = self.pinyin_permutation(word)
            cp = self.chaizi_permutation(word)
            for idx, key in enumerate(sp+pp+cp):
                Ac.add_word(key, (idx, key))
        Ac.make_automaton()
        return Ac

    def find_illegal_words(self,text):
        """
        构造非法词汇ac自动机

        :param :
        :return Ac: 非法词汇扩展Ac自动机
        """
        text = text.lower()
        text = self.replace_special_character(text)
        text = self.remove_punctation(text)
        text = self.remove_invalid_alphabet(text)
        pinyin = lazy_pinyin(text)[0]
        for end_index, (insert_order, original_value) in self.illegal_words_ac.iter(text):
            start_index = end_index - len(original_value) + 1
            print(original_value)
        for end_index, (insert_order, original_value) in self.illegal_words_ac.iter(pinyin):
            start_index = end_index - len(original_value) + 1
            print(original_value)


if __name__=='__main__':
    icd = IllegalCommentDetection()
    #print(icd.pinyin_permutation("洛奇"))
    #print(icd.chaizi_permutation("洛奇"))
    #print(icd.compare_bihua('裸', '果'))
    #print(icd.similarity_dict['裸'])
    #print(icd.similarity_permutation('你'))
    #print(icd.remove_invalid_alphabet('luoaaaliao'))
    #print(icd.illegal_words_list)
    #print(icd.find_illegal_words("luoaaa**liao"))
    #print(icd.find_illegal_words("我想衣果聊"))
    #print(icd.find_illegal_words("想棵聊"))
