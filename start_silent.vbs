' Silent launcher: backend + Cloudflare tunnel, tanpa jendela.
Set sh = CreateObject("WScript.Shell")
root = "C:\Users\Suran\Documents\absensi-murid"
py   = "C:\Users\Suran\AppData\Local\Python\pythoncore-3.14-64\python.exe"
cf   = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

sh.Run "cmd /c cd /d """ & root & "\backend"" && """ & py & """ serve.py", 0, False
sh.Run "cmd /c """ & cf & """ tunnel run absensi", 0, False