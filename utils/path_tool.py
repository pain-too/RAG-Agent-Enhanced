"""
为整个工程提供统一的绝对路径
"""
import os


#获取项目根目录的绝对路径
def get_project_root() -> str:
    current_file = os.path.abspath(__file__)#abs是绝对路径，__file__表示当前文件
    #当前文件在utils文件夹，往上跳两级就是根目录
    current_dir = os.path.dirname(current_file)
    project_root = os.path.dirname(current_dir)
    return(project_root)


#传递相对路径，得到绝对路径
def get_abs_path(relative_path: str) -> str:
    project_root = get_project_root()
    abs_path = os.path.join(project_root, relative_path)
    return(abs_path)

if __name__ == "__main__":
    print("绝对路径是",get_abs_path("utils/path_tool.py"))
