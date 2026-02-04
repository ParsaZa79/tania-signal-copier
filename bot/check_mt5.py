#!/usr/bin/env python3
"""Check MT5 connection and account balance using .env configuration."""

import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from tania_signal_copier.mt5_adapter import create_mt5_adapter


def main() -> None:
    # Get config from environment
    host = os.getenv("MT5_DOCKER_HOST", "localhost")
    port = int(os.getenv("MT5_DOCKER_PORT", "8001"))
    login = int(os.getenv("MT5_LOGIN", "0"))
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")

    print(f"MT5 Connection Check")
    print(f"====================")
    print(f"Host: {host}:{port}")
    print(f"Login: {login}")
    print(f"Server: {server}")
    print()

    # Create adapter for current platform
    mt5 = create_mt5_adapter(host=host, port=port)
    print(f"Platform: {sys.platform}")
    print(f"Adapter: {type(mt5).__name__}")
    print()

    # Initialize connection
    print("Initializing MT5 connection...")
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"Failed to initialize: {error}")
        sys.exit(1)
    print("Initialized successfully!")

    # Login/verify connection
    print("Verifying login...")
    if not mt5.login(login, password, server):
        error = mt5.last_error()
        print(f"Login verification failed: {error}")
        mt5.shutdown()
        sys.exit(1)
    print("Login verified!")
    print()

    # Get account info
    account = mt5.account_info()
    if account is None:
        print("Failed to get account info")
        mt5.shutdown()
        sys.exit(1)

    print("Account Information")
    print("===================")
    print(f"Login:    {account.login}")
    print(f"Name:     {account.name}")
    print(f"Server:   {account.server}")
    print(f"Currency: {account.currency}")
    print(f"Leverage: 1:{account.leverage}")
    print()
    print(f"Balance:  {account.balance:.2f} {account.currency}")
    print(f"Equity:   {account.equity:.2f} {account.currency}")
    print(f"Margin:   {account.margin:.2f} {account.currency}")
    print(f"Free:     {account.margin_free:.2f} {account.currency}")
    print()

    # Get open positions count
    positions = mt5.positions_total()
    orders = len(mt5.orders_get())
    print(f"Open positions: {positions}")
    print(f"Pending orders: {orders}")

    # Cleanup
    mt5.shutdown()
    print()
    print("Connection test successful!")


if __name__ == "__main__":
    main()
