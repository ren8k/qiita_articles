# Qiita Articles

本リポジトリでは，Qiita CLI と Github Actions を利用して Qiita の記事の投稿・更新を行っている．具体的には，以下の公式ドキュメントを参考にしている．

- [Qiita の記事を GitHub リポジトリで管理する方法](https://qiita.com/Qiita/items/32c79014509987541130)
- [qiita-cli](https://github.com/increments/qiita-cli)

## 記事のプレビュー

```
npx qiita preview
```

## 記事の作成（新規作成時）

- 記事のファイル名は XXX\_記事のファイル名.md としている．
- XXX は数字 3 桁，記事のファイル名は英語で記述する．
- 記事の markdown ファイルは `public` ディレクトリに作成される．

```
npx qiita new 記事のファイルのベース名
```

## 記事の作成（自身のテンプレート利用時）

- public/template.md を複製コピー．
- `ignorePublish`を `true` に設定する．

## 記事の投稿・更新

```
npx qiita publish 記事のファイルのベース名
```

## 記事の変更の反映について

- `main` または `master` ブランチに commit がある場合，自動で Qiita への記事の投稿・更新が行われる．
- 限定公開設定の際，`organization_url_name` に所属企業名を指定すると，ワークフローが失敗してしまう点に注意．

## 限定公開の解除時

- markdown ファイルの以下パラメーターを変更する
  - `private: true` を `false` に変更
  - `organization_url_name` を `所属企業名` に変更
