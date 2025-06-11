import os
import shutil
import schedule
import time
import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
from datetime import datetime
import paramiko
from scp import SCPClient
import re

# 設置日誌
logging.basicConfig(
    filename='file_transfer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class FileTransferApp:
    def __init__(self, root):
        self.root = root
        self.root.title("檔案傳輸應用程式")
        self.root.geometry("600x550")
        self.is_running = False
        self.schedule_thread = None

        # GUI 佈局
        tk.Label(root, text="目前時間:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.clock_label = tk.Label(root, text="", font=("Arial", 12))
        self.clock_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.update_clock()  # 啟動時鐘

        tk.Label(root, text="資料夾 A 路徑 (本地):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.folder_a_entry = tk.Entry(root, width=50)
        self.folder_a_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(root, text="資料夾 B 路徑 (遠端, 格式 user@host:/path):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.folder_b_entry = tk.Entry(root, width=50)
        self.folder_b_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(root, text="遠端伺服器密碼:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.password_entry = tk.Entry(root, width=50, show="*")
        self.password_entry.grid(row=3, column=1, padx=5, pady=5)

        tk.Label(root, text="資料夾 C 路徑 (本地):").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.folder_c_entry = tk.Entry(root, width=50)
        self.folder_c_entry.grid(row=4, column=1, padx=5, pady=5)

        tk.Label(root, text="傳輸時間 (HH:MM, 24小時制):").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.time_entry = tk.Entry(root, width=50)
        self.time_entry.grid(row=5, column=1, padx=5, pady=5)
        self.time_entry.insert(0, "00:00")  # 預設值

        self.start_button = tk.Button(root, text="啟動排程", command=self.start_schedule)
        self.start_button.grid(row=6, column=0, padx=5, pady=10)

        self.stop_button = tk.Button(root, text="停止排程", command=self.stop_schedule, state="disabled")
        self.stop_button.grid(row=6, column=1, padx=5, pady=10)

        self.log_text = scrolledtext.ScrolledText(root, height=10, width=60, state="disabled")
        self.log_text.grid(row=7, column=0, columnspan=2, padx=5, pady=5)

        # 初始日誌顯示
        self.update_log_display("應用程式已啟動，請輸入路徑、密碼和傳輸時間並啟動排程。\n")

    def update_clock(self):
        """更新時鐘顯示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.clock_label.config(text=current_time)
        self.root.after(1000, self.update_clock)  # 每秒更新

    def update_log_display(self, message):
        """更新 GUI 日誌顯示"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def validate_paths(self, folder_a, folder_c):
        """驗證本地資料夾路徑是否存在"""
        if not os.path.isdir(folder_a):
            self.update_log_display(f"錯誤：資料夾 A 不存在: {folder_a}")
            logging.error(f"資料夾 A 不存在: {folder_a}")
            return False
        if not os.path.isdir(folder_c):
            self.update_log_display(f"錯誤：資料夾 C 不存在: {folder_c}")
            logging.error(f"資料夾 C 不存在: {folder_c}")
            return False
        return True

    def validate_time(self, time_str):
        """驗證時間格式 HH:MM"""
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            self.update_log_display(f"錯誤：時間格式無效，必須為 HH:MM (例如 14:30)")
            logging.error(f"時間格式無效: {time_str}")
            return False
        try:
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                self.update_log_display(f"錯誤：時間範圍無效，小時 (00-23)，分鐘 (00-59)")
                logging.error(f"時間範圍無效: {time_str}")
                return False
            return True
        except ValueError:
            self.update_log_display(f"錯誤：時間格式無效，必須為 HH:MM")
            logging.error(f"時間格式無效: {time_str}")
            return False

    def get_txt_files(self, folder):
        """獲取資料夾中所有 .txt 檔案"""
        return [f for f in os.listdir(folder) if f.endswith('.txt') and os.path.isfile(os.path.join(folder, f))]

    def parse_remote_path(self, remote_path):
        """解析遠端路徑 user@host:/path"""
        try:
            user_host, path = remote_path.split(":", 1)
            user, host = user_host.split("@", 1)
            return user, host, path
        except ValueError:
            self.update_log_display(f"錯誤：遠端路徑格式無效: {remote_path}")
            logging.error(f"遠端路徑格式無效: {remote_path}")
            return None, None, None

    def transfer_files(self, folder_a, folder_b, folder_c, password):
        """執行檔案傳輸和移動"""
        try:
            if not self.validate_paths(folder_a, folder_c):
                return

            txt_files = self.get_txt_files(folder_a)
            if not txt_files:
                self.update_log_display("資料夾 A 中沒有 .txt 檔案")
                logging.info("資料夾 A 中沒有 .txt 檔案")
                return

            # 解析遠端路徑
            user, host, remote_path = self.parse_remote_path(folder_b)
            if not all([user, host, remote_path]):
                return

            # 建立 SSH 連線
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(host, username=user, password=password)
                with SCPClient(ssh.get_transport()) as scp:
                    for file in txt_files:
                        source_path = os.path.join(folder_a, file)
                        try:
                            scp.put(source_path, remote_path=remote_path)
                            self.update_log_display(f"成功傳輸檔案 {file} 到 {folder_b}")
                            logging.info(f"成功傳輸檔案 {file} 到 {folder_b}")

                            # 移動檔案到資料夾 C
                            destination_path = os.path.join(folder_c, file)
                            shutil.move(source_path, destination_path)
                            self.update_log_display(f"成功移動檔案 {file} 到 {folder_c}")
                            logging.info(f"成功移動檔案 {file} 到 {folder_c}")
                        except Exception as e:
                            self.update_log_display(f"傳輸或移動檔案 {file} 失敗: {e}")
                            logging.error(f"傳輸或移動檔案 {file} 失敗: {e}")
            except paramiko.AuthenticationException:
                self.update_log_display("錯誤：密碼驗證失敗")
                logging.error("密碼驗證失敗")
            except Exception as e:
                self.update_log_display(f"連線失敗: {e}")
                logging.error(f"連線失敗: {e}")
            finally:
                ssh.close()

        except Exception as e:
            self.update_log_display(f"執行過程中發生錯誤: {e}")
            logging.error(f"執行過程中發生錯誤: {e}")

    def run_schedule(self, folder_a, folder_b, folder_c, password, transfer_time):
        """運行排程"""
        schedule.every().day.at(transfer_time).do(self.transfer_files, folder_a=folder_a, folder_b=folder_b, folder_c=folder_c, password=password)
        self.update_log_display(f"排程已設置，每日 {transfer_time} 執行檔案傳輸")
        logging.info(f"排程已設置，每日 {transfer_time} 執行檔案傳輸")

        while self.is_running:
            schedule.run_pending()
            time.sleep(60)

    def start_schedule(self):
        """啟動排程"""
        folder_a = self.folder_a_entry.get().strip()
        folder_b = self.folder_b_entry.get().strip()
        folder_c = self.folder_c_entry.get().strip()
        password = self.password_entry.get().strip()
        transfer_time = self.time_entry.get().strip()

        if not folder_a or not folder_b or not folder_c or not password or not transfer_time:
            messagebox.showerror("錯誤", "請輸入所有資料夾路徑、密碼和傳輸時間！")
            self.update_log_display("錯誤：未提供所有路徑、密碼或傳輸時間")
            logging.error("未提供所有路徑、密碼或傳輸時間")
            return

        if not self.validate_time(transfer_time):
            return

        if self.is_running:
            messagebox.showinfo("提示", "排程已在運行中！")
            return

        self.is_running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        self.schedule_thread = threading.Thread(
            target=self.run_schedule,
            args=(folder_a, folder_b, folder_c, password, transfer_time),
            daemon=True
        )
        self.schedule_thread.start()
        self.update_log_display("排程已啟動")

    def stop_schedule(self):
        """停止排程"""
        if not self.is_running:
            messagebox.showinfo("提示", "排程未在運行！")
            return

        self.is_running = False
        schedule.clear()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.update_log_display("排程已停止")
        logging.info("排程已停止")

if __name__ == "__main__":
    root = tk.Tk()
    app = FileTransferApp(root)
    root.mainloop()