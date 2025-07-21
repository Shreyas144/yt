import streamlit as st
import yt_dlp
import os
import tempfile
import re
import os
import subprocess
import urllib.request

def setup_ffmpeg():
    ffmpeg_url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    extract_dir = "/tmp/ffmpeg"

    if not os.path.exists(extract_dir):
        os.makedirs(extract_dir, exist_ok=True)
        archive_path = "/tmp/ffmpeg.tar.xz"
        
        # Download FFmpeg archive
        urllib.request.urlretrieve(ffmpeg_url, archive_path)
        
        # Extract only the 'ffmpeg' binary
        subprocess.run(["tar", "-xJf", archive_path, "--strip-components=1", "-C", extract_dir, "ffmpeg-*-static/ffmpeg"])
        
        # Make it executable
        ffmpeg_bin = os.path.join(extract_dir, "ffmpeg")
        os.chmod(ffmpeg_bin, 0o755)
    
    # Add to PATH
    os.environ["PATH"] = extract_dir + os.pathsep + os.environ.get("PATH", "")

setup_ffmpeg()

# --- Session State Initialization ---
if 'cookie_data' not in st.session_state:
    st.session_state['cookie_data'] = None
if 'video_details' not in st.session_state:
    st.session_state['video_details'] = None
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = None

# --- Core Functions ---
def run_yt_dlp_command(url_or_query, ydl_opts, cookie_data=None):
    temp_cookie_path = None
    try:
        if cookie_data:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as temp_cookie_file:
                temp_cookie_path = temp_cookie_file.name
                temp_cookie_file.write(cookie_data)
            ydl_opts['cookiefile'] = temp_cookie_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if ydl_opts.get('skip_download', False):
                return ydl.extract_info(url_or_query, download=False)
            else:
                ydl.download([url_or_query])
                return {'status': 'success'}
    except Exception as e:
        return {'error': str(e)}
    finally:
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path)

def get_video_details(url, cookie_data=None):
    ydl_opts = {'noplaylist': True, 'skip_download': True}
    return run_yt_dlp_command(url, ydl_opts, cookie_data)

def search_youtube(query, cookie_data=None):
    ydl_opts = {'noplaylist': True, 'skip_download': True, 'default_search': 'ytsearch5'}
    return run_yt_dlp_command(query, ydl_opts, cookie_data)

# --- UI Rendering ---
st.set_page_config(page_title="Downloader", layout="wide")

# --- Sidebar with Instructions ---
with st.sidebar:
    st.header("How to use Cookies")
    st.markdown("""
    For private or age-restricted videos, you need to provide a cookie file. This is a safe way to authenticate without sharing your password.

    **Easiest Method (Google Chrome):**
    1.  Install the <a href="https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank">Get cookies.txt LOCALLY</a> extension.
    2.  Go to YouTube.com and log in.
    3.  Click the extension's icon and then **Export**.
    4.  Upload the downloaded `cookies.txt` file using the uploader below.
    """, unsafe_allow_html=True)

# --- Main Page Layout ---
cookie_file = st.file_uploader(
    "Upload cookies.txt (for private or age-restricted videos)",
    type=['txt'],
    key="cookie_uploader"
)
if cookie_file is not None:
    st.session_state['cookie_data'] = cookie_file.getvalue().decode('utf-8')
    st.toast("Cookies loaded.", icon="🍪")

col1, col2 = st.columns([0.92, 0.08])

with col1:
    user_input = st.text_input("Paste a YouTube URL or search for a video", key="url_input_main", label_visibility="collapsed")

with col2:
    if st.button("🔍", key="search_button"):
        st.session_state.video_details = None
        st.session_state.search_results = None
        is_url = re.match(r'https?://[\w\.-]+\.\w+', user_input)
        
        if is_url:
            details = get_video_details(user_input, cookie_data=st.session_state.get('cookie_data'))
            if 'error' in details:
                error_msg = details['error'].lower()
                if 'authentication' in error_msg or 'sign in' in error_msg:
                    st.toast("Authentication required. Please upload a valid cookie file.", icon="🔒")
                else:
                    st.toast("Video unavailable. Searching for alternatives...", icon="💡")
                
                title_search = details.get('title', user_input)
                search_results = search_youtube(title_search, cookie_data=st.session_state.get('cookie_data'))
                if 'error' in search_results:
                    st.session_state.search_results = {'error': 'double_failure'}
                else:
                    st.session_state.search_results = search_results
            else:
                st.session_state.video_details = details
        else:
            st.session_state.search_results = search_youtube(user_input, cookie_data=st.session_state.get('cookie_data'))

st.markdown("--- ")

# --- Dynamic Content Display Area ---

if st.session_state.search_results and st.session_state.search_results.get('error') == 'double_failure':
    st.error("**YouTube is blocking requests from this server.** To continue, please upload a cookies.txt file.")

elif st.session_state.search_results and 'entries' in st.session_state.search_results:
    st.subheader("Search Results")
    for item in st.session_state.search_results['entries']:
        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            st.image(item.get('thumbnail'))
        with col2:
            st.write(f"**{item.get('title')}**")
            st.write(f"_By {item.get('uploader', 'N/A')}_")
            if st.button("Select this video", key=f"select_{item.get('id')}"):
                st.session_state.video_details = get_video_details(item.get('webpage_url'), cookie_data=st.session_state.get('cookie_data'))
                st.session_state.search_results = None
                st.rerun()

elif st.session_state.video_details:
    video_details = st.session_state.video_details
    if 'error' in video_details:
        st.error("An unexpected error occurred while fetching video details.")
    else:
        st.image(video_details.get('thumbnail'), use_container_width=True)
        video_tab, audio_tab = st.tabs(["Video (MP4)", "Audio (MP3)"])

        with tempfile.TemporaryDirectory() as temp_dir:
            with video_tab:
                video_formats = sorted([
                    f for f in video_details.get('formats', [])
                    if f.get('ext') == 'mp4' and f.get('vcodec') != 'none'
                ], key=lambda x: x.get('height', 0), reverse=True)

                if video_formats:
                    format_options = {}
                    for f in video_formats:
                        label = f"{f.get('height')}p"
                        if f.get('fps', 0) > 30: label += f" ({f.get('fps')}fps)"
                        if f.get('acodec') == 'none': label += " (Needs FFmpeg)"
                        if label not in format_options: format_options[label] = f['format_id']
                    
                    selected_label = st.selectbox("Video Quality", options=list(format_options.keys()), label_visibility="collapsed")
                    
                    if st.button("Download Video", key="download_video", use_container_width=True):
                        placeholder = st.empty()
                        placeholder.info("Preparing download...")
                        format_id = format_options[selected_label]
                        ydl_opts = {
                            'format': f'{format_id}+bestaudio/best' if '+bestaudio' not in format_id else format_id,
                            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                            'merge_output_format': 'mp4',
                        }
                        result = run_yt_dlp_command(video_details.get('webpage_url'), ydl_opts, st.session_state.get('cookie_data'))
                        
                        downloaded_files = os.listdir(temp_dir)
                        if not downloaded_files:
                            error_msg = result.get('error', 'File not found after download attempt.').lower()
                            if 'authentication' in error_msg or 'sign in' in error_msg:
                                placeholder.error("Download failed. Your cookie file may be invalid or expired.")
                            else:
                                placeholder.error(f"Download failed: {result.get('error')}")
                        else:
                            for filename in downloaded_files:
                                file_path = os.path.join(temp_dir, filename)
                                with open(file_path, "rb") as f:
                                    st.download_button(
                                        label=f"Download {filename}",
                                        data=f,
                                        file_name=filename,
                                        mime="video/mp4",
                                        use_container_width=True
                                    )
                            placeholder.empty()

            with audio_tab:
                audio_formats = sorted([
                    f for f in video_details.get('formats', [])
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('ext') in ['m4a', 'webm']
                ], key=lambda x: x.get('abr', 0), reverse=True)

                audio_options = {"Best Available": "bestaudio/best"}
                for f in audio_formats:
                    label = f"{int(f.get('abr', 0))}kbps ({f.get('ext')})"
                    if label not in audio_options:
                        audio_options[label] = f['format_id']

                selected_audio_label = st.selectbox("Audio Quality", options=list(audio_options.keys()), label_visibility="collapsed")

                if st.button("Download Audio as MP3", key="download_mp3", use_container_width=True):
                    placeholder = st.empty()
                    placeholder.info("Preparing download...")
                    format_id = audio_options[selected_audio_label]
                    ydl_opts = {
                        'format': format_id,
                        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
                    }
                    result = run_yt_dlp_command(video_details.get('webpage_url'), ydl_opts, st.session_state.get('cookie_data'))
                    
                    downloaded_files = os.listdir(temp_dir)
                    if not downloaded_files:
                        error_msg = result.get('error', 'File not found after download attempt.').lower()
                        if 'authentication' in error_msg or 'sign in' in error_msg:
                            placeholder.error("Download failed. Your cookie file may be invalid or expired.")
                        else:
                            placeholder.error(f"Download failed: {result.get('error')}")
                    else:
                        if result and 'error' in result:
                            st.toast(f"Conversion to MP3 failed. Offering raw audio file.", icon="⚠️")
                        for filename in downloaded_files:
                            file_path = os.path.join(temp_dir, filename)
                            with open(file_path, "rb") as f:
                                st.download_button(
                                    label=f"Download {filename}",
                                    data=f,
                                    file_name=filename,
                                    mime="audio/mpeg" if ".mp3" in filename else "application/octet-stream",
                                    use_container_width=True
                                )
                        placeholder.empty()
