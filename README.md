# Presentes do Telegram — catálogo

Site estático (pt-BR) com todas as coleções de Presentes colecionáveis (NFT) do Telegram: modelos, fundos, símbolos, raridade, imagens/animações, preço mínimo e tiragem.

- Build: `python3 build.py` (requer Pillow) → gera `docs/` (servido pelo GitHub Pages).
- `python3 build.py render` re-renderiza a partir de `docs/data.json` sem baixar nada.
- Atualização diária: copie `ci/rebuild.yml` para `.github/workflows/rebuild.yml` (o token usado na criação não tinha o escopo `workflow`).

Fontes públicas, sem chave de API: api.changes.tg / cdn.changes.tg (dados, PNG, Lottie), portal-market.com (floor em TON), t.me/nft (tiragem). Projeto não oficial.
