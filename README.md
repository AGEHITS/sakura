# S.A.K.U.R.A.
"Softly Assisting, Keeping You Uplifted, Relieved, and At Peace."  
（そっと寄り添い、あなたを元気づけ、癒しと安らぎを届ける）

## 概要
LINEでメッセージを送るとAIが返信してくれる仕組みの作成

| version | 説明 |
| ---- | ---- |
| 1.0 | 初期開発 |
| 1.1 | 仕様追加（過去2往復分の会話を踏まえて返信） |
| 1.2 | 仕様追加（AI側からLINE送信） |


## 技術スタック
- Python
- LINE Messaging API
- Google Gemini API
- Webhook対応のサーバー（Google Cloud Functions）  
  ※月間100万回の無料呼び出しと、月間360,000 GB-秒の無料コンピューティングタイムあり
- gcloud scheduler（cron的な仕組み）

## プログラム
### プログラム一覧
| プログラム名 | 説明 |
| ---- | ---- |
| main.py | メインプログラム |
| geminiapi_ver.py | geminiapiの利用可能バージョンを確認可能なプログラム |
| secret_setup.py | secretを保管するプログラム（現在動かない） |

### 機能一覧
| 機能名 | 実行契機 | 説明 |
| ---- | ---- | ---- |
| line_webhook | こちらからのLINE送信時 | LINE返信機能 |
| send_random_message | Cloud Scheduler（毎時） | LINE送信判定機能（送信要否を抽選し、Cloud Tasksにn分後に送信依頼 |
| send_message_task | Cloud Tasks | LINE送信機能 |

## 開発ステップ
1. 準備

- LINE Developersコンソールでチャンネルを作成
- Google Cloud Consoleでプロジェクトを作成
  https://console.cloud.google.com/
- APIの有効化
  - Cloud Functions API
  - Cloud Build API
  - Secret Manager API
  - Cloud Deployment Manager V2 API
  - Gemini API
- サービスアカウントの作成
  - IAMと管理 → サービスアカウント → 「サービスアカウントを作成」
  - 必要な権限（Cloud Functions管理者、Secret Manager管理者）を付与
  - JSON形式の秘密鍵をダウンロード

2. 環境構築

```
# デフォルトリージョンとゾーンの設定
gcloud config set compute/region asia-northeast1
gcloud config set compute/zone asia-northeast1-a

# 必要なAPIを一括で有効化
gcloud services enable \
    compute.googleapis.com \
    cloudfunctions.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Pythonの仮想環境作成
python3 -m venv gcp-bot-env
source gcp-bot-env/bin/activate

# 必要なライブラリのインストール
pip install functions-framework flask requests google-cloud-secret-manager google-generativeai
pip install google-cloud-secret-manager google-cloud-core

# Google Cloud認証の設定
gcloud auth application-default login
```

3. デプロイ準備
```
# デプロイ用フォルダ作成
mkdir line-ai-bot
cd line-ai-bot

# プログラム配置
#このリポジトリのline-ai-bot配下のファイルを配置する
※secret_setup.pyのKEY情報は更新する。
Google Gemini APIキーの取得は、Google AI Studioにアクセスして取得
https://makersuite.google.com/app/apikey

# Google Secret Manager APIキー保存スクリプトの実行
python3 secret_setup.py

# プロジェクトのデフォルトサービスアカウントに権限を付与
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com \
    --role=roles/cloudfunctions.invoker

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member=serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor
```

4.デプロイコマンド
```
cd line-ai-bot
# line_webhook（AIが返信）
gcloud functions deploy line_webhook \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --source . \
    --entry-point webhook \
    --memory 256MB \
    --timeout 60s \
    --region asia-northeast1 \
    --set-env-vars LINE_CHANNEL_SECRET=aaaaa,LINE_CHANNEL_ACCESS_TOKEN=bbbbb,GEMINI_API_KEY=ccccc

# send_random_message
gcloud functions deploy send_random_message \
    --gen2 \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --source . \
    --entry-point send_random_message \
    --memory 256MB \
    --timeout=3600 \
    --region asia-northeast1 \
    --set-env-vars LINE_CHANNEL_SECRET=aaaaa,LINE_CHANNEL_ACCESS_TOKEN=bbbbb,GEMINI_API_KEY=ccccc,USER_ID=dddddd

# send_message_task
gcloud functions deploy send_message_task \
    --gen2 \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --source . \
    --entry-point send_message_task \
    --memory 256MB \
    --timeout=3600 \
    --region asia-northeast1 \
    --set-env-vars LINE_CHANNEL_SECRET=aaaaa,LINE_CHANNEL_ACCESS_TOKEN=bbbbb,GEMINI_API_KEY=ccccc,USER_ID=dddddd

# Cloud Tasks のキュー作成（初回のみ）
## キュー作成
gcloud tasks queues create line-message-queue \
  --location=asia-northeast1
## 環境変数の設定
TASK_QUEUE=projects/winged-will-455109-k9/locations/asia-northeast1/queues/line-message-queue
TASK_TARGET_URL=https://asia-northeast1-winged-will-455109-k9.cloudfunctions.net/send_message_task

# スケジュール登録（初回のみ）
## スケジュール登録
gcloud scheduler jobs create http send-line-message \
    --schedule="0 * * * *" \
    --uri "https://xxxxxxxxx/send_random_message" \
    --http-method POST \
    --location=asia-northeast1
```

5.Webhook URLの確認
```
gcloud functions describe line_webhook
```
6.ログの確認
```
gcloud functions logs read line_webhook --location=asia-northeast1
```
7.再接続時
```
gcloud auth login
```
8.スケジューラ関連
```
# ジョブリスト参照
gcloud scheduler jobs list
# ジョブの手動実行
gcloud scheduler jobs run send-line-message --location=asia-northeast1
# ジョブ実行ログ
gcloud scheduler jobs describe send-line-message --location=asia-northeast1
# ジョブ削除
gcloud scheduler jobs delete send-line-message --location=asia-northeast1
```
9.gcloud task関連
```
## キューの存在確認
gcloud tasks queues list --location=asia-northeast1
## タスク一覧の確認
gcloud tasks list --queue=line-message-queue --location=asia-northeast1
```
10.その他
```
## デプロイした関数一覧
gcloud functions list --v2
## 手動実行＆確認
gcloud scheduler jobs run send-line-message --location=asia-northeast1
gcloud tasks list --queue=line-message-queue --location=asia-northeast1
gcloud logging read   'resource.type="cloud_run_revision"
   AND resource.labels.service_name="send-random-message"'   --limit 3   --order desc | grep chance
```
