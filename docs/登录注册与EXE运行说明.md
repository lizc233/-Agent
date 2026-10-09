# 登录注册与 EXE 运行说明

## 登录和注册

程序启动后先显示登录窗口。用户编号对应 MySQL `customer_user.user_code`，登录成功后 Agent 使用该行的主键 `id` 查询 `customer_order.user_id`，不会从界面任意指定用户主键。

已有测试用户（例如 `U10001`）的 `password_hash` 初始为空。第一次使用时切换到注册，填写原用户编号、昵称和至少 6 位密码；程序只为该用户设置密码，原有订单关系保持不变。以后直接使用用户编号和密码登录。

全新注册用户不会自动生成订单。订单数据仍由 MySQL 初始化脚本或独立后端维护，本 Agent 项目不承担新增订单业务。

## 密码安全

密码使用 PBKDF2-SHA256、随机盐和 210000 次迭代保存。数据库不保存明文密码，也不能从哈希恢复原密码。

## EXE 位置

可执行文件位于：

`dist/KangarooCustomerAgent/KangarooCustomerAgent.exe`

必须保留整个 `KangarooCustomerAgent` 文件夹，不能只复制单个 EXE。`.env` 放在 EXE 同级目录，用于配置 MySQL 和 DeepSeek；不要将带真实密码的 `.env` 上传到 Git。

首次打包后，如果目录中只有 `.env.example`，请把项目根目录中已经填写好的 `.env` 复制到 `dist/KangarooCustomerAgent/.env`。其中 `MYSQL_HOST`、`MYSQL_DATABASE`、`MYSQL_USER` 和 `MYSQL_PASSWORD` 必须填写；`DEEPSEEK_API_KEY` 可以为空，程序会使用离线回答模式。

## 重新打包

双击 `build_exe.bat`。虚拟环境、pip 缓存、PyInstaller 缓存、临时目录和产物都位于 D 盘项目目录。
