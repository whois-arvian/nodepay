import requests
import json

print("For Active New Account Nodepay | Multiple Account!")

# Buka file accounts.txt untuk membaca daftar akun
try:
    with open('accounts.txt', 'r') as file:
        # Membaca dan memproses setiap akun dari file
        # Ubah cara membaca file
        account_list = file.read().split('--------------------------------------------------\n')

        if not account_list:
            print("File 'accounts.txt' kosong. Tambahkan akun ke file dan coba lagi.")
            exit()

        # Simpan np_token ke file terpisah
        with open('new_np_tokens.txt', 'w') as token_file:
            for account in account_list:
                # Parsing data akun
                account_data = {}
                for line in account.splitlines():
                    if line.strip():  # Abaikan baris kosong
                        key, value = line.split(": ", 1)
                        account_data[key.strip()] = value.strip()

                # Periksa apakah email dan password ada
                email = account_data.get("Email")
                password = account_data.get("Password")

                if not email or not password:
                    print(f"Akun tidak valid: {account}")
                    print("Pastikan setiap akun memiliki Email dan Password.")
                    print('------------------------------------')
                    continue

                # URL dan Headers untuk request login
                url = "https://api.nodepay.org/api/auth/login?"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }

                # Data untuk request login
                payload = {
                    "email": email,
                    "password": password
                }

                try:
                    # Kirim POST request
                    response = requests.post(url, headers=headers, json=payload)

                    # Periksa status response
                    if response.status_code == 200:
                        response_json = response.json()
                        np_token = response_json.get('np_token')  # Cek di response JSON

                        if np_token:
                            print(f"Berhasil login untuk akun {email}.")
                            print(f"np_token: {np_token}")
                            print('------------------------------------')

                            # Simpan np_token ke file
                            token_file.write(f"{email}: {np_token}\n")
                        else:
                            print(f"Tidak ditemukan np_token untuk akun {email}.")
                            print(f"Response: {response_json}")
                            print('------------------------------------')
                    else:
                        print(f"Gagal login untuk akun {email}.")
                        print(f"Status Code: {response.status_code}")
                        print(f"Response Text: {response.text}")
                        print('------------------------------------')

                except requests.exceptions.RequestException as e:
                    print(f"Request error untuk akun {email}: {str(e)}")
                    print('------------------------------------')

except FileNotFoundError:
    print("File 'accounts.txt' tidak ditemukan. Pastikan file tersebut ada di direktori yang sama dengan script.")
except Exception as e:
    print(f"Terjadi error: {str(e)}")
