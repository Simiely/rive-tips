# runtime-check · Rive 运行时验收页

**用途**：导出 `.riv` 后，用**官方运行时**确认「画板数、渲染、错误」——编辑器能看见不代表能交付。

详细背景见 [`../../docs/导出规则与交付验收.md`](../../docs/导出规则与交付验收.md)。

## 使用

```bash
cd tools/runtime-check
npm init -y
npm i @rive-app/webgl2          # 国内可加 --registry=https://registry.npmmirror.com
python -m http.server 8123      # 或任意静态服务器
```

浏览器打开：

```
http://127.0.0.1:8123/index.html?f=你的文件.riv
```

页面会显示：

- **ARTBOARD_COUNT** —— `.riv` 里实际存在的画板数（对照源文件的画板数，少了就是导出规则问题）
- 每个画板的名字
- 默认画板的实时渲染（中文是否豆腐块一眼可见）
- 加载错误

## 无头截图（可选）

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless=new --disable-gpu --enable-unsafe-swiftshader `
  --virtual-time-budget=12000 --window-size=1400,760 `
  --screenshot="D:\out\check.png" `
  "http://127.0.0.1:8123/index.html?f=test.riv"
```

## 判读

| 现象 | 结论 |
|---|---|
| ARTBOARD_COUNT 比源文件少 | 画板没进包：需标记为组件或拆文件 |
| 中文是 ▯ | 字体没内嵌：Type 改 Embedded |
| LOAD_ERROR | 文件损坏或脚本未签名 |
| 一切正常 | 可以交付 |
