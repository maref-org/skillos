# skillos-contrib

Community-contributed and project-specific skills for the SkillOS ecosystem.

## Structure

| Directory | Description |
|-----------|-------------|
| `athena/` | Athena platform integration skills |
| `openhuman/` | OpenHuman ecosystem skills |
| `maref/` | MAREF integration skills |
| `media-production/` | Video and media production skills |
| `marketing/` | Marketing and content generation skills |

## Installation

Skills in this repository can be loaded by SkillOS via the Registry protocol:

```python
from skillos import SkillKernel

kernel = SkillKernel()
kernel.load_skill("skillos-contrib://media-production/phone-video-factory")
```

## Contributing

See [SkillOS Contributing Guide](https://github.com/skillos-team/skillos/blob/main/CONTRIBUTING.md).

## License

AGPL-3.0 — same as SkillOS core.
