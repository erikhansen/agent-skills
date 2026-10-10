# Agent Skills

A collection of [Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for Claude Code and other agents that support the `SKILL.md` format.

## Layout

```
skills/
  <skill-name>/
    SKILL.md        # required: frontmatter (name, description) + instructions
    scripts/        # optional: executable helpers the skill calls
    references/     # optional: docs/data loaded on demand
    assets/         # optional: templates and other files used in output
```

Each folder under `skills/` is self-contained, and its name matches the `name` in its `SKILL.md`.

## Skills

| Skill | Description |
|---|---|
| [openai-image-styles](skills/openai-image-styles) | Restyle photos into 30+ art styles with OpenAI's image models, keep faces recognizable, and publish a swipeable gallery. Keychain-based API key onboarding and per-run cost reporting. |

## Installing a skill

Copy or symlink a skill folder into your personal skills directory:

```bash
git clone git@github.com:erikhansen/agent-skills.git
ln -s "$PWD/agent-skills/skills/openai-image-styles" ~/.claude/skills/openai-image-styles
```

Use `.claude/skills/` inside a project instead to scope a skill to that project.

## Adding a skill

1. Create `skills/<skill-name>/SKILL.md`.
2. Don't commit secrets, API keys, personal photos or client details. Skills should read credentials at runtime (env var, OS keychain).
3. Add a row to the table above.

## License

[MIT](LICENSE)
