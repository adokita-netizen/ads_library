# A97: CI/CDパイプライン完全自動化

## 優先度: 🅱️ B（重要）

## 問題
- GitHub Actionsワークフローは設定済みだが、完全な自動デプロイが検証されていない
- push→ビルド→テスト→デプロイの一気通貫フローが未確認

## 対象ファイル
- `.github/workflows/` 配下
- `docker/Dockerfile.backend`
- `docker/Dockerfile.frontend`
- `docker/Dockerfile.worker`
- `docker/Dockerfile.lambda`
- `terraform/` 配下

## タスク

### Task 1: 既存ワークフロー確認
- 現在のGitHub Actionsの設定内容を確認
- トリガー条件（push/PR/manual）の確認

### Task 2: ビルドパイプライン検証
- Frontend: `npm run build` → S3アップロード → CloudFrontインバリデーション
- Backend: Docker build → ECR push → Lambda更新
- Worker: Docker build → ECR push → ECSタスク定義更新

### Task 3: テストステージ追加
- Pythonバックエンドテスト（pytest）
- フロントエンドテスト（vitest + playwright）
- テスト失敗時はデプロイをブロック

### Task 4: デプロイステージ検証
- staging → production のプロモーション
- ロールバック手順の確認

## 完了条件
- [x] mainへのpushで自動ビルド→テスト→デプロイが実行される
- [x] テスト失敗時にデプロイがブロックされる
- [x] デプロイ成功がSlack/GitHub通知される
- [x] ロールバック手順が文書化されている

## 制約
- 本番環境への影響を最小限にする
- 既存のTerraform設定と整合性を保つ

## Status
Completed (2026-03-05, workflow hardening + rollback runbook)
