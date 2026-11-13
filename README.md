# Langbox

**Linux向けプログラミング言語環境のセットアップランチャー**

Debian / Ubuntu (`apt`) および Arch Linux (`pacman`) 環境において、主要なプログラミング言語から低レイヤ・WebAssembly・アセンブリ・ハードウェア記述言語まで、開発環境のチェックとワンクリック導入・削除を行うGUIランチャーです。

---

## 主な特徴

* **ディストリビューション自動判別:** `/etc/os-release` を解析し、`apt` または `pacman` を自動で切り替えます。
* **約40種類の開発環境に対応:** Web・スクリプト系から、C/C++/Rust/Zig、WebAssembly、アセンブリ、関数型、Verilog/VHDLまで幅広いカテゴリを網羅しています。
* **リアルタイム検索＆カテゴリ絞り込み:** 言語名や用途キーワードによるインクリメンタル検索に対応しています。
* **GUIからの安全な権限昇格:** `pkexec`（Polkit）を使用してGUIダイアログから管理者権限を取得し、パッケージのインストール・アンインストールを実行します（非GUI環境では `sudo` にフォールバック）。
* **リアルタイムログ表示:** パッケージマネージャの実行ログをアプリ内のコンソールにリアルタイム出力します。
* **外部ライブラリ不要:** Python標準ライブラリ（`tkinter`）のみで動作するため、軽量かつOSへの組み込みが容易です。

---

## 対応ディストリビューション

* **Debian / Ubuntu 系** (`debian`, `ubuntu`, `linuxmint`, `pop`, `elementary`)
* **Arch Linux 系** (`arch`, `manjaro`, `endeavouros`, `garuda`)

---

## 動作要件

Python 3.8 以上および以下のシステムパッケージが必要です。

* **Debian / Ubuntu 系:**
  ```bash
  sudo apt update && sudo apt install -y python3 python3-tk policykit-1 fonts-noto-cjk
  ```
* **Arch Linux 系:**
  ```bash
  sudo pacman -Syu python tk polkit noto-fonts-cjk
  ```

システムに組み込まれている場合は、アプリケーションメニューから **Langbox** を起動するか、ターミナルで `langbox` を実行します。

---

## カスタマイズ（言語の追加）

`languages.json` に以下の形式でオブジェクトを追加するだけで、UIに新しい言語やツールが自動的に反映されます。
