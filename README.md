# 轻羽阅读器

一个轻量的本地 TXT 小说阅读器，使用 Python 标准库 `tkinter` 开发，无第三方运行依赖。

## 功能

- 导入 `.txt` 小说文件
- 自动识别常见章节标题并显示在左侧目录
- 调节字号大小
- 夜间模式 / 日间模式切换
- 自动记忆上次打开的文件和阅读章节

## 运行

```powershell
python main.py
```

## 打包 EXE

```powershell
python -m pip install pyinstaller
.\build_exe.bat
```

## 快捷键

- `Ctrl + O`：打开 TXT
- `Ctrl + +`：增大字号
- `Ctrl + -`：减小字号
- `Ctrl + D`：切换夜间模式
- `↑ / ↓`：上一页 / 下一页
- `← / →`：上一章 / 下一章

## 发布到 GitHub 前建议

- 保留源码文件：`main.py`、`README.md`、`build_exe.bat`
- 不提交打包产物和缓存：`dist/`、`build/`、`__pycache__/`
- 如果本地 `tools/` 只是打包时临时装出来的依赖目录，也不要提交
