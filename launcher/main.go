package main

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	webview "github.com/jchv/go-webview2"
)

func newCmd(name string, args ...string) *exec.Cmd {
	cmd := exec.Command(name, args...)
	if runtime.GOOS == "windows" {
		cmd.SysProcAttr = hiddenProc()
	}
	return cmd
}

const appPort = 5000

// ── 路径 ──────────────────────────────────────────────────────────────────────

func appDir() string {
	exe, _ := os.Executable()
	return filepath.Dir(exe)
}

// ── Python 检测 ────────────────────────────────────────────────────────────────

func findPython() string {
	names := []string{"python3", "python"}
	if runtime.GOOS == "windows" {
		names = []string{"python", "python3", "py"}
	}
	for _, name := range names {
		if p, err := exec.LookPath(name); err == nil {
			return p
		}
	}
	return ""
}

// ── 依赖检测 ──────────────────────────────────────────────────────────────────

func checkMissing(py string) []string {
	script := `
import sys
pkgs=[('flask','flask'),('flask_socketio','flask-socketio'),
      ('torch','torch'),('torchvision','torchvision')]
missing=[p for m,p in pkgs if __import__('importlib').util.find_spec(m) is None]
print(','.join(missing))
`
	out, err := exec.Command(py, "-c", script).Output()
	if err != nil {
		return nil
	}
	s := strings.TrimSpace(string(out))
	if s == "" {
		return nil
	}
	return strings.Split(s, ",")
}

// ── 服务器等待 ────────────────────────────────────────────────────────────────

func waitForServer(port int, timeout time.Duration) bool {
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if c, err := net.DialTimeout("tcp", addr, time.Second); err == nil {
			c.Close()
			return true
		}
		time.Sleep(300 * time.Millisecond)
	}
	return false
}

// ── HTML 模板 ─────────────────────────────────────────────────────────────────

const baseStyle = `<meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,Arial;background:#0e0e0e;color:#eaeaea;
     display:flex;flex-direction:column;align-items:center;justify-content:center;
     height:100vh}
.logo{font-size:52px;margin-bottom:12px}
.title{font-size:22px;font-weight:bold;color:#9fb1ff;margin-bottom:6px}
.sub{font-size:12px;color:#555;margin-bottom:28px;letter-spacing:.5px}
.spinner{width:32px;height:32px;border:3px solid #222;border-top-color:#9fb1ff;
         border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.msg{font-size:13px;color:#888;margin-top:16px}
button{margin-top:20px;padding:10px 28px;background:#2b3a55;color:#fff;
       border:1px solid #3b4a66;border-radius:6px;font-size:14px;cursor:pointer}
button:hover{background:#3b4a66}
button:disabled{opacity:.4;cursor:not-allowed}
ul{list-style:none;margin:16px 0;text-align:left}
li{padding:4px 0;font-size:13px;color:#ccc}
li::before{content:"⚠ ";color:#f0a;font-size:11px}
.log{width:560px;max-height:260px;overflow-y:auto;background:#111;
     border:1px solid #333;border-radius:6px;padding:10px;
     font-family:Consolas,monospace;font-size:11px;color:#aaa;
     text-align:left;margin-top:16px;display:none}
.log p{margin:1px 0;white-space:pre-wrap;word-break:break-all}
.ok{color:#4caf50!important;border-color:#3a6a45!important}
.err-txt{color:#f44}
</style>`

const loadingHTML = `<!DOCTYPE html><html><head>` + baseStyle + `</head><body>
<div class="logo">🧠</div>
<div class="title">CortexNodus</div>
<div class="sub">可视化神经网络设计工具</div>
<div class="spinner"></div>
<div class="msg">正在启动服务，请稍候…</div>
</body></html>`

func installHTML(missing []string) string {
	items := ""
	for _, p := range missing {
		items += "<li>" + p + "</li>"
	}
	return `<!DOCTYPE html><html><head>` + baseStyle + `</head><body>
<div class="logo">🧠</div>
<div class="title">CortexNodus</div>
<div class="sub">检测到以下依赖缺失，需要安装后才能运行</div>
<ul>` + items + `</ul>
<button id="btn" onclick="doInstall()">一键安装依赖</button>
<div class="log" id="log"></div>
<script>
function doInstall(){
  document.getElementById('btn').disabled=true;
  document.getElementById('btn').textContent='安装中…';
  document.getElementById('log').style.display='block';
  __go_install();
}
function appendLog(l){
  var b=document.getElementById('log');
  var p=document.createElement('p');p.textContent=l;
  b.appendChild(p);b.scrollTop=b.scrollHeight;
}
function onDone(ok){
  var b=document.getElementById('btn');
  if(ok){
    b.textContent='✓ 安装完成，点击重启';
    b.className='ok';b.disabled=false;
    b.onclick=function(){__go_restart()};
  }else{
    b.textContent='安装失败，重试';
    b.disabled=false;b.onclick=doInstall;
  }
}
</script>
</body></html>`
}

func newWindow(title string, w, h int, fixed bool) webview.WebView {
	hint := webview.HintNone
	if fixed {
		hint = webview.HintFixed
	}
	wv := webview.NewWithOptions(webview.WebViewOptions{
		Debug: false,
		WindowOptions: webview.WindowOptions{
			Title:  title,
			Width:  uint(w),
			Height: uint(h),
			Center: true,
		},
	})
	wv.SetSize(w, h, hint)
	return wv
}

func errorHTML(msg string) string {
	return `<!DOCTYPE html><html><head>` + baseStyle + `</head><body>
<div class="logo">❌</div>
<div class="title err-txt">启动失败</div>
<div class="msg">` + msg + `</div>
</body></html>`
}

// ── 主逻辑 ────────────────────────────────────────────────────────────────────

func main() {
	dir := appDir()

	// 1. 找 Python
	py := findPython()
	if py == "" {
		w := newWindow("CortexNodus", 500, 300, true)
		defer w.Destroy()
		w.SetHtml(errorHTML("未找到 Python，请安装 Python 3.8+ 并加入 PATH"))
		w.Run()
		return
	}

	// 2. 检测依赖
	missing := checkMissing(py)
	if len(missing) > 0 {
		w := newWindow("CortexNodus — 安装依赖", 640, 580, true)
		defer w.Destroy()
		w.SetHtml(installHTML(missing))

		w.Bind("__go_install", func() {
			go func() {
				req := filepath.Join(dir, "requirements.txt")
				cmd := newCmd(py, "-m", "pip", "install", "-r", req, "--no-warn-script-location")
				pipe, _ := cmd.StdoutPipe()
				cmd.Stderr = cmd.Stdout
				cmd.Start()

				buf := make([]byte, 512)
				for {
					n, err := pipe.Read(buf)
					if n > 0 {
						line := strings.TrimRight(string(buf[:n]), "\r\n")
						safe := strings.ReplaceAll(line, "`", "'")
						js := fmt.Sprintf("appendLog(`%s`)", safe)
						w.Dispatch(func() { w.Eval(js) })
					}
					if err != nil {
						break
					}
				}
				ok := cmd.Wait() == nil
				js := fmt.Sprintf("onDone(%v)", ok)
				w.Dispatch(func() { w.Eval(js) })
			}()
		})

		w.Bind("__go_restart", func() {
			exe, _ := os.Executable()
			exec.Command(exe).Start()
			os.Exit(0)
		})

		w.Run()
		return
	}

	// 3. 启动 Flask
	flask := newCmd(py, filepath.Join(dir, "app.py"))
	flask.Dir = dir
	if err := flask.Start(); err != nil {
		w := newWindow("CortexNodus", 500, 300, true)
		defer w.Destroy()
		w.SetHtml(errorHTML("无法启动 Flask：" + err.Error()))
		w.Run()
		return
	}
	defer func() {
		if flask.Process != nil {
			flask.Process.Kill()
		}
	}()

	// 4. 显示加载页，等待服务就绪后跳转
	w := newWindow("CortexNodus", 1440, 900, false)
	defer w.Destroy()
	w.SetHtml(loadingHTML)

	go func() {
		if waitForServer(appPort, 60*time.Second) {
			url := fmt.Sprintf("http://127.0.0.1:%d", appPort)
			w.Dispatch(func() { w.Navigate(url) })
		} else {
			html := errorHTML("Flask 服务启动超时，请运行 python app.py 查看错误")
			w.Dispatch(func() { w.SetHtml(html) })
		}
	}()

	w.Run()
}
