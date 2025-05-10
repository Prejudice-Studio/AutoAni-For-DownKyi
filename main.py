import os
import re
import requests
import json
from pathlib import Path
from urllib.parse import quote
from textwrap import fill

# 配置文件处理
def get_config_path():
    return Path(__file__).resolve().parent / "config.json"

def load_config():
    config_file = get_config_path()
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if isinstance(config, dict):
                    return config
                print("⚠️ 配置文件格式错误，已重置")
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 配置文件读取错误: {e}")
    return {}

def shorten(text, width=60, placeholder="..."):
    """自定义缩短文本函数"""
    if len(text) <= width:
        return text
    return text[:width - len(placeholder)] + placeholder

def save_config(config):
    try:
        with open(get_config_path(), 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"⚠️ 保存配置失败: {e}")

# Bangumi API 交互
def search_bangumi(keyword, page=1):
    """搜索番剧（支持分页）"""
    url = f"https://api.bgm.tv/search/subject/{quote(keyword)}?type=2&responseGroup=large&start={(page-1)*10}"
    headers = {"User-Agent": "bangumi-renamer/1.0"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("list", [])
        total = data.get("results", 0)
        total_pages = max(1, (total + 9) // 10)
        
        print(f"\n🔍 搜索结果 (第{page}页/共{total_pages}页):")
        for i, item in enumerate(results[:10], 1):
            name = item.get('name_cn') or item.get('name', '未知')
            print(f"\n{i}. {name} (ID: {item.get('id', '未知')})")
            print(f"   📅 放送: {item.get('air_date', '未知')}")
            print(f"   ⭐ 评分: {item.get('rating', {}).get('score', '无')} ({item.get('rating', {}).get('total', 0)}人评分)")
            print(f"   📺 集数: {item.get('total_episodes', '未知')}")
            
            # 显示前5个标签
            if item.get('tags'):
                print(f"   🏷️ 标签: {', '.join(tag['name'] for tag in item['tags'][:5])}")
            
            # 缩短的简介（最多3行）
            summary = item.get('summary', '无')
            shortened = shorten(summary, width=60, placeholder="...")
            print(f"   📖 简介: {shortened}")
        
        return results, total_pages
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return [], 1

def fetch_bangumi_data(anime_id, access_token=None):
    """获取番剧详细信息（完整版）"""
    headers = {
        "User-Agent": "bangumi-renamer/1.0",
        "accept": "application/json"
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    
    try:
        # 获取基本信息
        subject_url = f"https://api.bgm.tv/v0/subjects/{anime_id}"
        subject_res = requests.get(subject_url, headers=headers)
        subject_res.raise_for_status()
        anime_data = subject_res.json()

        # 获取分集信息
        episodes_url = f"https://api.bgm.tv/v0/episodes?subject_id={anime_id}&limit=100"
        episodes_res = requests.get(episodes_url, headers=headers)
        episodes_res.raise_for_status()
        episodes_data = episodes_res.json().get("data", [])

        # 旧版API备用
        if not episodes_data:
            episodes_url = f"https://api.bgm.tv/subject/{anime_id}/episodes"
            episodes_res = requests.get(episodes_url, headers=headers)
            episodes_res.raise_for_status()
            episodes_data = episodes_res.json()

        episodes = {}
        for ep in episodes_data:
            if isinstance(ep, dict) and ep.get("type") == 0:  # 正片
                ep_num = ep.get("sort") or ep.get("ep")
                if ep_num is not None:
                    ep_name = ep.get("name_cn") or ep.get("name") or f"第{ep_num}话"
                    episodes[int(ep_num)] = ep_name

        # 获取完整标签信息
        tags_url = f"https://api.bgm.tv/v0/subjects/{anime_id}/tags"
        tags_res = requests.get(tags_url, headers=headers)
        if tags_res.status_code == 200:
            tags_data = tags_res.json()
            anime_data['tags'] = [tag['name'] for tag in tags_data.get('data', [])]
        else:
            anime_data['tags'] = []

        return anime_data, episodes
    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return None, {}

def display_anime_info(anime_data, episodes):
    """完整显示番剧信息"""
    print("\n" + "="*80)
    print("🎬 番剧详细信息".center(80))
    print("="*80)
    
    print(f"\n📛 中文标题: {anime_data.get('name_cn', '无')}")
    print(f"🔠 原版标题: {anime_data.get('name', '无')}")
    print(f"📅 放送日期: {anime_data.get('date', '未知')}")
    print(f"⭐ 评分: {anime_data.get('rating', {}).get('score', '无')} ({anime_data.get('rating', {}).get('total', 0)}人评分)")
    print(f"📺 总集数: {len(episodes)}")
    print(f"🏷️ 排名: {anime_data.get('rank', '无')}")
    
    print("\n🏷️ 标签: ", end="")
    if anime_data.get('tags'):
        print(", ".join(anime_data['tags'][:15]))  # 最多显示15个标签
        if len(anime_data['tags']) > 15:
            print(f"  (共{len(anime_data['tags'])}个标签，显示前15个)")
    else:
        print("无")
    
    print("\n📖 完整简介:")
    print(anime_data.get('summary', '无'))
    
    print("\n📺 分集列表:")
    for num, title in sorted(episodes.items()):
        print(f"  第{str(num).zfill(2)}话: {title}")
    
    print("="*80 + "\n")

def rename_files(directory, subgroup, prefix, season, episode_titles, use_bangumi, start_offset=0, add_titles=True, hdr_resolution=None):
    """执行文件重命名
    :param hdr_resolution: 用户指定的HDR视频分辨率（如1080）
    """
    # 增强版正则，匹配各种格式：
    # 1. 正片 第X话 标题.编码.质量信息.ext
    # 2. 第X话.编码.质量信息.ext
    pattern = re.compile(
        r".*(?:正片\s*)?(?:第(\d+)话|EP(\d+))(?:\s*(.*?))?(?:\.(AVC|HEVC|H\.264|H\.265))?(?:\.(HDR|SDR))?(?:\.(\d{3,4}P|4[Kk]|8[Kk])(?:\s*超高清)?)?(?:\s*(真彩|Hi10P|高码率|高画质))*\.([a-zA-Z0-9]+)$",
        re.IGNORECASE
    )
    preview = []
    
    for filename in os.listdir(directory):
        clean_name = filename.strip('\ufeff').strip()
        match = pattern.match(clean_name)
        if not match:
            print(f"⏭️ 跳过: '{filename}'")
            continue

        # 提取信息
        original_num = int(match.group(1) or match.group(2))
        original_title = match.group(3).strip() if match.group(3) else ""
        codec = match.group(4)  # AVC/HEVC等
        hdr_flag = match.group(5)  # HDR/SDR
        resolution = match.group(6)  # 1080P/4K等
        extra_flags = match.group(7)  # 真彩/Hi10P等
        ext = match.group(8).lower()  # 扩展名

        # 计算集数
        episode_num = original_num + (start_offset - 1) if start_offset > 0 else original_num
        
        # 确定标题
        final_title = ""
        if add_titles:
            if use_bangumi and episode_titles:
                final_title = episode_titles.get(original_num, original_title)
            else:
                final_title = original_title
        
        # 处理分辨率逻辑
        resolution_parts = []
        if hdr_flag and hdr_resolution:  # 如果是HDR视频且用户指定了分辨率
            resolution_parts.append(f"{hdr_resolution}P")
        elif resolution:  # 其他情况使用检测到的分辨率
            resolution = resolution.upper()
            if resolution == '4K':
                resolution = '2160P'
            elif resolution == '8K':
                resolution = '4320P'
            resolution_parts.append(resolution)
        
        # 构建质量信息部分
        quality_parts = []
        if codec:
            quality_parts.append(codec.upper())
        if resolution_parts:
            quality_parts.extend(resolution_parts)
        
        hdr_detected = bool(hdr_flag) or (extra_flags and "真彩" in extra_flags)
        if hdr_detected:
            quality_parts.append("HDR")
        
        quality_suffix = "." + ".".join(quality_parts) if quality_parts else ""
        
        # 构建新文件名
        parts = []
        if subgroup:
            parts.append(f"[{subgroup}]")
        if prefix:
            parts.append(prefix)
        parts.append(f"S{str(season).zfill(2)}E{str(episode_num).zfill(2)}" if season else f"E{str(episode_num).zfill(2)}")
        if final_title.strip():
            parts.append(final_title.strip())
        
        new_name = " ".join(parts) + quality_suffix + f".{ext}"
        preview.append((filename, new_name))

    if not preview:
        print("❌ 没有可重命名的文件")
        return False

    print("\n📢 重命名预览:")
    for old, new in preview:
        print(f"🔄 '{old}' → '{new}'")

    confirm = input("\n✅ 确认执行？(Y/n, 默认Y): ").strip().lower()
    if confirm not in ('', 'y', 'yes'):
        print("❌ 已取消")
        return False

    for old, new in preview:
        try:
            os.rename(
                os.path.join(directory, old),
                os.path.join(directory, new))
            print(f"✅ 已重命名: '{old}' → '{new}'")
        except Exception as e:
            print(f"❌ 失败: {e}")
    
    return True

def main():
    print("🎬 Bangumi 番剧文件重命名工具 v4.5".center(80, '='))
    print("="*80 + "\n")
    config = load_config()
    
    # 检查Access Token
    if not config.get("access_token"):
        print("ℹ️ 未配置Access Token，部分功能可能受限")
        print("ℹ️ 可在 https://next.bgm.tv/demo/access-token 申请")
        if input("是否现在配置？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
            token = input("请输入Access Token: ").strip()
            if token:
                config["access_token"] = token
                save_config(config)
                print("✅ Token已保存")
    
    while True:
        try:
            # 获取文件夹路径
            path = input("\n📂 输入文件夹路径（输入exit退出）: ").strip()
            if path.lower() == 'exit':
                break
            if not os.path.isdir(path):
                print("❌ 目录无效")
                continue

            # 所有确认步骤默认Y
            use_bangumi = input("🌐 使用Bangumi数据？(Y/n): ").strip().lower() in ('', 'y', 'yes')
            anime_data = None
            episode_titles = {}
            
            if use_bangumi:
                page = 1
                while True:
                    query = input("\n🔍 输入番剧名/ID/n下一页/p上一页: ").strip()
                    
                    if query.lower() == 'n':
                        page += 1
                    elif query.lower() == 'p':
                        page = max(1, page-1)
                    elif query.isdigit():
                        anime_data, episode_titles = fetch_bangumi_data(query, config.get("access_token"))
                        if anime_data:
                            display_anime_info(anime_data, episode_titles)
                            if input("\n✅ 使用此信息？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
                                prefix = anime_data.get('name_cn') or anime_data.get('name')
                                break
                        print("❌ 未找到该ID的番剧")
                        continue
                    
                    results, total_pages = search_bangumi(query if query not in ('n', 'p') else "", page)
                    if not results:
                        print("❌ 无结果")
                        continue
                        
                    choice = input("选择编号(1-10)/n下一页/p上一页: ").strip().lower()
                    
                    if choice.isdigit() and 1 <= int(choice) <= len(results):
                        selected = results[int(choice)-1]
                        anime_data, episode_titles = fetch_bangumi_data(selected["id"], config.get("access_token"))
                        if anime_data:
                            display_anime_info(anime_data, episode_titles)
                            if input("\n✅ 使用此信息？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
                                prefix = anime_data.get('name_cn') or anime_data.get('name')
                                break
                    elif choice == 'n':
                        page = min(page+1, total_pages)
                    elif choice == 'p':
                        page = max(1, page-1)
                
                if not anime_data:
                    print("❌ 无法获取番剧信息")
                    use_bangumi = False
                    prefix = input("\n🏷 输入文件名前缀: ").strip()
                else:
                    if input(f"\n🏷 使用'{prefix}'作为前缀？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
                        pass
                    else:
                        prefix = input("请输入前缀: ").strip()
            else:
                prefix = input("\n🏷 输入文件名前缀: ").strip()
            
            # 获取其他参数
            subgroup = input("🔖 输入SubGroup(如VCB): ").strip()
            
            # 添加标题选项
            add_titles = input("📝 是否添加集标题？(Y/n): ").strip().lower() in ('', 'y', 'yes')
            
            # 添加季数（默认Y）
            season = None
            if input("\n📺 添加季数？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
                while True:
                    try:
                        season = int(input("🔢 输入季数(如1): ").strip())
                        break
                    except ValueError:
                        print("❌ 请输入数字")
                        
            # 新增：HDR分辨率设置
            hdr_resolution = None
            if input("\n🎬 是否包含HDR视频？(y/N): ").strip().lower() in ('y', 'yes'):
                while True:
                    try:
                        hdr_resolution = input("请输入HDR视频的分辨率(如1080/2160): ").strip()
                        if not hdr_resolution.isdigit():
                            print("❌ 请输入数字")
                            continue
                        break
                    except ValueError:
                        print("❌ 请输入有效数字")
            
            # 起始集数偏移（默认N）
            start_offset = 0
            if input("\n🔢 是否设置起始集数偏移？(y/N): ").strip().lower() in ('y', 'yes'):
                while True:
                    try:
                        start_offset = int(input("请输入起始集数(如13表示E01→E13): ").strip())
                        if start_offset < 1:
                            print("❌ 请输入≥1的数字")
                            continue
                        break
                    except ValueError:
                        print("❌ 请输入有效数字")
            
            # 执行重命名（默认Y）
            if input("\n✅ 确认执行重命名？(Y/n): ").strip().lower() in ('', 'y', 'yes'):
                success = rename_files(
                    path, subgroup, prefix, season, 
                    episode_titles, use_bangumi, 
                    start_offset, add_titles, hdr_resolution
                )
                
                if success:
                    print("\n" + "🎉 操作成功！".center(80, '=') + "\n")
                else:
                    print("\n" + "⚠️ 操作未完成".center(80, '=') + "\n")
            else:
                print("\n❌ 已取消重命名")
                
        except KeyboardInterrupt:
            print("\n⏹️ 操作中断")
        except Exception as e:
            print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
