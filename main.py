import os
import re
import requests
import json
from pathlib import Path

# 获取脚本文件所在目录的路径
def get_config_file_path():
    script_dir = Path(__file__).resolve().parent  # 获取当前脚本文件的目录
    return script_dir / "config.json"  # 修改文件名为 config.json

# 从配置文件加载access token
def load_config():
    config_file = get_config_file_path()
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
                # 检查读取到的数据是否为字典
                if isinstance(config_data, dict):
                    return config_data
                else:
                    print("配置文件格式错误，预计为字典类型，已重置配置。")
                    return {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"配置文件读取错误: {e}, 正在创建新的配置文件...")
    return {}

# 保存配置到config.json
def save_config(config):
    config_file = get_config_file_path()
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"保存配置文件时发生错误: {e}")

# 请求Bangumi API并获取数据
def fetch_bangumi_data(anime_id, access_token):
    """从Bangumi API获取动画和剧集数据，带有access token。"""
    headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'Authorization': f"Bearer {access_token}",
        'User-Agent': 'Prejudice-Studio/AutoAni-For-DownKyi (https://github.com/Prejudice-Studio/AutoAni-For-DownKyi)'
    }
    
    base_url = f"https://api.bgm.tv/v0/subjects/{anime_id}"  # 获取动画的基本信息
    episodes_url = f"https://api.bgm.tv/v0/episodes?subject_id={anime_id}"  # 获取该动画的所有剧集（章节）
    
    try:
        # 获取动画基础信息
        anime_response = requests.get(base_url, headers=headers)
        anime_response.raise_for_status()  # 如果响应码不是 2xx 会抛出异常
        anime_data = anime_response.json()
        
        # 获取剧集信息
        episodes_response = requests.get(episodes_url, headers=headers)
        episodes_response.raise_for_status()  # 如果响应码不是 2xx 会抛出异常
        episodes_data = episodes_response.json()
        
        episodes = {}

        # 收集剧集标题（优先中文标题，若无则使用原标题）
        for ep in episodes_data["data"]:
            if ep.get('type') != 0:
                continue
            ep_number = ep['sort']
            episode_title = ep['name_cn'] if ep['name_cn'] != "" else ep['name']
            episode_title = episode_title if episode_title != "" else f"第{ep_number}话"
            episodes[ep_number] = episode_title
        
        return anime_data, episodes
    except requests.RequestException as e:
        print(f"无法获取 Bangumi 数据: {e}")
        return None, {}

# 重命名文件
def rename_files_in_directory(directory, prefix, season, episode_titles, anime_data, add_episode_title):
    # 定义文件名匹配规则
    pattern_full = re.compile(r"(?:.+ )?第(\d+)话 (.+)\.(\w+)")  # 匹配 "正片 第X话 abcdefg.mp4" 或 "第X话 abcdefg.mp4"
    pattern_partial = re.compile(r"(?:.+ )?第(\d+)话\.(\w+)")  # 匹配 "正片 第X话.mp4" 或 "第X话.mp4"

    # 记录用户对部分匹配的决策
    user_decision = None

    # 准备预览列表
    preview_changes = []

    try:
        # 遍历目录中的所有文件
        for filename in os.listdir(directory):
            try:
                match_full = pattern_full.match(filename)
                match_partial = pattern_partial.match(filename)

                if match_full:
                    # 提取文件名中的编号、名称和扩展名
                    number = int(match_full.group(1))
                    name = match_full.group(2)
                    extension = match_full.group(3)

                    # 从Bangumi获取剧集标题，如果没有则使用文件名中的名称
                    episode_title = episode_titles.get(number, name) if add_episode_title else ""

                    # 格式化新文件名，并在集数前添加零
                    season_prefix = f"S{str(season).zfill(2)}" if season else ""
                    if prefix and season and episode_title:
                        new_filename = f"{prefix} {season_prefix}E{str(number).zfill(2)} {episode_title}.{extension}"
                    elif prefix and season:
                        new_filename = f"{prefix} {season_prefix}E{str(number).zfill(2)}.{extension}"
                    elif prefix and episode_title:
                        new_filename = f"{prefix} E{str(number).zfill(2)} {episode_title}.{extension}"
                    elif prefix:
                        new_filename = f"{prefix} E{str(number).zfill(2)}.{extension}"
                    elif season and episode_title:
                        new_filename = f"{season_prefix}E{str(number).zfill(2)} {episode_title}.{extension}"
                    elif season:
                        new_filename = f"{season_prefix}E{str(number).zfill(2)}.{extension}"
                    else:
                        new_filename = f"E{str(number).zfill(2)}.{extension}"

                    preview_changes.append((filename, new_filename))

                elif match_partial:
                    # 提取文件名中的编号和扩展名
                    number = int(match_partial.group(1))
                    extension = match_partial.group(2)

                    # 从Bangumi获取剧集标题，如果没有则使用默认名称
                    episode_title = episode_titles.get(number, "") if add_episode_title else ""

                    if user_decision is None:
                        # 提示用户是否强制重命名部分匹配文件
                        response = input(f"检测到文件 '{filename}' 只有编号，是否强制重命名？(y/n，留空默认 y): ").strip().lower() or 'y'
                        if response == 'y':
                            user_decision = True
                        elif response == 'n':
                            user_decision = False
                        else:
                            print("无效的输入，请输入 'y' 或 'n'。")
                            continue

                    if user_decision:
                        season_prefix = f"S{str(season).zfill(2)}" if season else ""
                        if episode_title == "":
                            episode_title = f"第{number}话"
                        if prefix and season and episode_title:
                            new_filename = f"{prefix} {season_prefix}E{str(number).zfill(2)} {episode_title}.{extension}"
                        elif prefix and season:
                            new_filename = f"{prefix} {season_prefix}E{str(number).zfill(2)}.{extension}"
                        elif prefix and episode_title:
                            new_filename = f"{prefix} E{str(number).zfill(2)} {episode_title}.{extension}"
                        elif prefix:
                            new_filename = f"{prefix} E{str(number).zfill(2)}.{extension}"
                        elif season and episode_title:
                            new_filename = f"{season_prefix}E{str(number).zfill(2)} {episode_title}.{extension}"
                        elif season:
                            new_filename = f"{season_prefix}E{str(number).zfill(2)}.{extension}"
                        else:
                            new_filename = f"E{str(number).zfill(2)}.{extension}"

                        preview_changes.append((filename, new_filename))
                    else:
                        print(f"跳过文件: '{filename}'")
                else:
                    print(f"跳过文件: '{filename}'，不符合重命名规则")

            except Exception as e:
                print(f"处理文件 '{filename}' 时发生错误: {e}")
                continue

        # 显示重命名预览并确认
        print("以下是重命名预览:")
        for old_name, new_name in preview_changes:
            print(f"'{old_name}' → '{new_name}'")

        confirm = input("是否确认执行重命名？(y/n，留空默认 y): ").strip().lower() or 'y'
        if confirm == 'y':
            for old_name, new_name in preview_changes:
                try:
                    old_path = os.path.join(directory, old_name)
                    new_path = os.path.join(directory, new_name)
                    os.rename(old_path, new_path)
                    print(f"文件重命名: '{old_name}' → '{new_name}'")
                except Exception as e:
                    print(f"重命名文件 '{old_name}' 时发生错误: {e}")
                    continue
        elif confirm == 'n':
            print("已取消重命名操作。")
        else:
            print("无效的输入，请输入 'y' 或 'n'。")

    except Exception as e:
        print(f"处理文件夹 '{directory}' 时发生错误: {e}")



# 主程序
if __name__ == "__main__":
    config = load_config()

    # 首次启动时询问填写access token
    if not config.get('access_token'):
        print("首次启动，您需要提供 Bangumi Access Token。")
        while True:
            ACCESS_TOKEN = input("请输入 Bangumi 动画的 Access Token: ").strip()
            if ACCESS_TOKEN:
                config['access_token'] = ACCESS_TOKEN
                break
            else:
                print("Access Token 不能为空！")
        save_config(config)

    # 开始执行重命名操作
    while True:
        try:
            folder_path = input("请输入包含要重命名文件的文件夹路径（或输入 'exit' 退出程序）：").strip()
            if folder_path.lower() == 'exit':
                print("程序已退出。")
                break
            if not os.path.isdir(folder_path):
                print("指定的文件夹路径无效，请重新输入。")
                continue

            use_bangumi = input("是否使用 Bangumi 获取剧集标题？(y/n，留空默认 y): ").strip().lower() or 'y'
            
            if use_bangumi == 'y':
                bangumi_id = input("请输入 Bangumi 动画 ID（用于获取剧集标题）：").strip()
                if not bangumi_id.isdigit():
                    print("无效的 Bangumi 动画 ID，请重试。")
                    continue

                # 获取 Bangumi 数据
                anime_data, episode_titles = fetch_bangumi_data(bangumi_id, config['access_token'])

                if anime_data is None:
                    print("未能获取到动画信息，已取消操作。")
                    continue

                if anime_data:
                    anime_title = anime_data.get('name_cn') or anime_data.get('name', '未知')
                    print(f"动画标题: {anime_title}")
                    print(f"简介: {anime_data.get('summary', '无详细信息')}\n")
                    print("剧集信息:")
                    for sort, title in episode_titles.items():
                        print(f"第{sort}集: {title}")

                    # 询问是否将动画标题作为前缀
                    use_title_as_prefix = input("是否使用动画标题作为重命名前缀？(y/n，留空默认 y): ").strip().lower() or 'y'
                    if use_title_as_prefix == 'y':
                        prefix = anime_title
                    else:
                        prefix = input("请输入重命名文件名前缀（可留空，留空默认无前缀）：").strip()
                else:
                    print("未能获取到动画信息，已取消操作。")
                    continue
            else:
                print("跳过获取剧集标题。")
                episode_titles = {}
                anime_data = None
                prefix = input("请输入重命名文件名前缀（可留空，留空默认无前缀）：").strip()

            add_season = input("是否在集数前添加季数？(y/n，留空默认添加): ").strip().lower() or 'y'
            if add_season == 'y':
                try:
                    season = int(input("请输入季数（例如 1 表示第 1 季）：").strip())
                except ValueError:
                    print("无效的季数输入，请输入一个整数。")
                    continue
            else:
                season = None

            # 询问是否要添加章节标题
            add_episode_title = input("是否在文件名中添加章节标题？(y/n，留空默认 y): ").strip().lower() or 'y'
            if add_episode_title == 'y':
                add_episode_title = True
            else:
                add_episode_title = False

            # 处理文件重命名
            if anime_data is None:
                print("跳过 Bangumi 标题的使用。")
                rename_files_in_directory(folder_path, prefix, season, episode_titles, None, add_episode_title)
            else:
                rename_files_in_directory(folder_path, prefix, season, episode_titles, anime_data, add_episode_title)
            print("重命名处理完成")
        except Exception as e:
            print(f"程序执行过程中发生错误: {e}")
            continue
