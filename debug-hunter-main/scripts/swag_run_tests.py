#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SWAG QA 部門自動化測試與漏洞掃描啟動器
用途: 供 QA 工程師快速調用，執行金流、博弈、直播與前端交互的自動化掃描與 PoC 驗證。
"""

import os
import sys
import argparse
import subprocess

def run_semgrep_scan(target_dir):
    print(f"[*] 正在對 {target_dir} 執行 SWAG 專屬 Semgrep 安全規則掃描...")
    # 這裡可以調用預先寫好的 semgrep 規則
    rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rules", "semgrep")
    if not os.path.exists(rules_path):
        print("[-] 未找到 Semgrep 規則目錄。")
        return False
        
    cmd = f"semgrep --config {rules_path} {target_dir}"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode == 0:
            print("[+] Semgrep 掃描完成，未發現已知代碼特徵漏洞。")
            return True
        else:
            print("[!] Semgrep 掃描完成，發現潛在代碼漏洞！")
            return False
    except FileNotFoundError:
        print("[-] 系統未安裝 semgrep，請先執行 'pip install semgrep' 安裝。")
        return False

def run_poc_script(poc_name):
    poc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents", poc_name)
    if not os.path.exists(poc_path):
        # 嘗試在 scripts 或 examples 目錄中尋找
        poc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", poc_name)
        
    if not os.path.exists(poc_path):
        print(f"[-] 未找到指定的 PoC 腳本: {poc_name}")
        return False
        
    print(f"[*] 正在啟動自動化漏洞復現 PoC: {poc_name} ...")
    try:
        result = subprocess.run([sys.executable, poc_path], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode == 1:
            print("🔴 [VULNERABLE] 漏洞復現成功！")
            return False
        else:
            print("🟢 [SECURE] 漏洞無法復現（系統已具備防禦）。")
            return True
    except Exception as e:
        print(f"[-] 執行 PoC 出錯: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="SWAG QA 自動化測試與漏洞掃描工具")
    subparsers = parser.add_subparsers(dest="command", help="執行模式")
    
    # 掃描模式
    scan_parser = subparsers.add_parser("scan", help="執行靜態代碼掃描")
    scan_parser.add_argument("--target", required=True, help="掃描的目標代碼目錄")
    
    # PoC 復現模式
    poc_parser = subparsers.add_parser("poc", help="執行特定漏洞復現 PoC")
    poc_parser.add_argument("--name", required=True, help="PoC 腳本名稱 (例如: poc_late_betting.py)")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        run_semgrep_scan(args.target)
    elif args.command == "poc":
        run_poc_script(args.name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
