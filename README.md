# InstallerX Revived — 个人 AOSP 构建

这是基于 [InstallerX Revived](https://github.com/wxxsfxyzm/InstallerX-Revived) 的个人构建仓库。

- 只在 Actions 中手动运行 **Manual AOSP Build**，没有每天定时或代码推送触发的发布。
- 每次先合并上游的 `main`，只构建包名 `com.android.packageinstaller` 的 `PackageInstaller.apk`。
- 只把 APK 发到配置的 Telegram 私聊；不生成 Google APK、Magisk 模块 ZIP 或 GitHub Release。
- PR 检查和 CodeQL 安全扫描继续保留；它们的测试构建不发送 Telegram 消息。
- 应用本身的安装功能保持原样，变更仅针对这个 fork 的构建与分发。

## 第一次使用

### 1. 配置 Telegram

创建自己的 Bot，先打开与它的私聊并发送 `/start`。准备 Bot Token 和你自己的**正整数个人 Chat ID**。

到本仓库 **Settings → Secrets and variables → Actions → New repository secret** 添加：

| Secret | 内容 |
| --- | --- |
| `BOT_TOKEN` | 你的 Telegram Bot Token |
| `CHAT_ID` | 你的个人数字 Chat ID，不是用户名、群组 ID 或频道 ID |

脚本先通过 Telegram `getChat` 确认目标是私聊，再向同一个 ID 发送 APK 或失败通知。只配置一个收件人。
不再需要 `API_ID`、`API_HASH`、`BOT_CI_SESSION` 或 `MY_CHAT_ID`。

### 2. 一次性准备 APK 签名密钥

签名密钥是你的 APK 的身份凭证。自己的后续版本需要沿用同一把密钥，才能按 Android 的正常规则覆盖更新。
请长期备份密钥文件和密码；不要在每次构建时重新生成。

**个人签名不等于手机厂商的系统签名。** 同样叫 `com.android.packageinstaller` 并不代表可以直接覆盖手机自带安装器。
系统替换仍取决于原有签名、ROM 和你的安装方式，参见[上游系统集成说明](https://wxxsfxyzm.github.io/InstallerX-Revived-Website/guide/system-integration)。

如果已经有需要沿用的签名密钥，请使用原密钥，不要执行下面的生成命令。

在你自己的电脑安装 JDK（项目使用 JDK 25），打开终端，切换到**仓库目录以外**的一个私人目录。
执行以下命令生成密钥（Windows PowerShell、macOS 和 Linux 均可）：

```text
keytool -genkeypair -keystore installerx-personal.p12 -storetype PKCS12 -alias installerx -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=InstallerX Personal"
```

按提示设置并确认密码。这个 PKCS12 密钥库的密钥密码与密钥库密码相同。
命令只需执行一次；生成的 `installerx-personal.p12` 是需要备份的私钥文件。

将文件编码为 Base64，供 GitHub Secret 保存。Base64 只是编码，仍属于私钥，不能提交到仓库：

**Windows PowerShell：** 在密钥所在目录运行，结果会复制到剪贴板，直接粘贴到 Secret 的值中。

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path (Get-Location) "installerx-personal.p12"))) | Set-Clipboard
```

**macOS / Linux：** 在密钥所在目录运行，然后复制生成文件的全部内容。

```bash
base64 < installerx-personal.p12 | tr -d '\n' > installerx-personal.base64
```

在同一个 GitHub Actions Secrets 页面添加：

| Secret | 内容 |
| --- | --- |
| `SIGNING_KEY_STORE_BASE64` | 上面得到的完整 Base64 文本 |
| `SIGNING_STORE_PASSWORD` | 生成密钥时设置的密码 |
| `SIGNING_KEY_ALIAS` | `installerx` |
| `SIGNING_KEY_PASSWORD` | 与 `SIGNING_STORE_PASSWORD` 相同的密码 |

使用已有密钥时，填写它实际的别名和密码。密钥缺失、密码或别名不正确时，构建会失败，不会默默改用临时 debug 签名。

工作流仅将密钥解码到 runner 临时目录，构建结束后删除。不会把密钥作为 artifact 上传，也不会发送到 Telegram。

### 3. 手动构建

1. 打开本仓库的 **Actions**。如果 fork 的工作流尚未启用，按 GitHub 的提示启用。
2. 选择 **Manual AOSP Build → Run workflow**，选择 `main` 并运行。
3. 等待上游合并和构建完成。Bot 会把 `PackageInstaller.apk` 发到你的私聊，附带版本和上游提交号。
4. Telegram 配置验证成功后，如果后续合并、签名、构建或发送失败，会尽力向同一个私聊发送日志链接；发送失败会让工作流显示失败。

无需手动创建发布或模块模板分支。

## 上游同步与版本

合并仅发生在本次 Actions 的工作目录，不会自动提交或推送到你的 `main`。
应用源码按 Git 的正常合并规则更新；本 fork 的 `.github/` 自动化配置始终保留，包括已删除的自动发布工作流。
其他路径发生冲突时立即停止，需要先在 fork 中解决冲突再运行，不会继续用旧源码构建。

沿用原 fork 的版本格式：`222222.33 (YYYYMMDD)`，versionCode 为 `YYYYMMDD`，日期使用北京时间。
两次同日构建使用相同的 versionCode；原工作流也是这一规则。
最新上游源码按 Stable 构建类型编译，并不表示这些上游提交已经通过正式稳定版发布验证。

## 常见问题

- **Bot 无法联系你：** 确认你已私聊发送 `/start`，没有屏蔽 Bot，且 `CHAT_ID` 是自己的个人 ID。
- **APK 太大：** 当前使用 Telegram 官方托管 Bot API，单个文件最多 50 MB。超过限制会明确失败，不会改为投递到其他地方。
- **依赖下载返回 401 / 403：** 仓库通过 GitHub Packages 下载依赖，保留了 `GITHUB_ACTOR`、`GITHUB_TOKEN` 和 `packages: read` 配置。实际能否访问仍由依赖包的权限决定，按日志核查。
- **找不到 keytool：** 安装 JDK，并把其 `bin` 目录加入 PATH；也可直接使用该目录下的 `keytool` / `keytool.exe`。
- **签名不同导致无法覆盖安装：** 沿用已安装版本的签名密钥；新生成的个人密钥不能模拟原系统或原作者的签名。

## 原项目与参考资料

应用功能说明见 [上游文档](docs/README_CN.md)。本项目保留原有 GPL-3.0 许可证及作者署名。

- [Android 官方：为应用签名](https://developer.android.com/studio/publish/app-signing)
- [Telegram Bot API](https://core.telegram.org/bots/api#senddocument)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
