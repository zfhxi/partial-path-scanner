from ruamel.yaml import YAML as RYAML
from .logger import getLogger


class YAMLLoader(object):
    def __init__(self, file_dir, logger=None):
        self.file_dir = str(file_dir)
        self.data = {}
        self.ryaml = RYAML(typ='rt')
        self.ryaml.default_flow_style = False
        self.ryaml.allow_unicode = True
        self.logger = logger or getLogger(__name__)

    def get(self) -> dict:
        with open(self.file_dir, 'r', encoding='utf-8') as file:
            self.data = self.ryaml.load(file.read())
        return self.data

    def update(self, _dict, root_key_seqs: list = None):
        """
        更改 yaml 文件中的值, 并且保留注释内容
        """
        try:
            # 读取原数据
            data = self.get()
            # 合并新数据和原数据
            if root_key_seqs is None or len(root_key_seqs) == 0:
                data.update(_dict)
            else:
                p_data = data
                for k in root_key_seqs:
                    p_data = p_data[k]
                p_data.update(_dict)
            # 写入新数据，同时保留原注释
            with open(self.file_dir, 'w', encoding='utf-8') as f:
                self.ryaml.dump(data, f)
            return True
        except Exception as e:
            self.logger.error(f"YAML写入失败: {e}")
            return False

    def delete(self, folder, root_key_seqs: list = None):
        """
        删除 yaml 文件中的值
        """
        try:
            # 读取原数据
            data = self.get()
            if root_key_seqs is None or len(root_key_seqs) == 0:  # //如果未指定，则跳过
                return False
            else:
                p_data = data
                for k in root_key_seqs:
                    p_data = p_data[k]
                p_data.pop(folder)
            # 写入新数据，同时保留原注释
            with open(self.file_dir, 'w', encoding='utf-8') as f:
                self.ryaml.dump(data, f)
            return True
        except Exception as e:
            self.logger.error(f"YAML写入失败: {e}")
            return False
