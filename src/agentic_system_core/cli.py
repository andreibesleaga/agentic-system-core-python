from . import WELLKNOWN_SUFFIX, LINK_RELATION, __version__


def main():
    print(f"Agentic System Core (agsc) - v{__version__}")
    print("-" * 38)
    print("This is a name reservation. No runtime is published yet.")
    print(f"Well-known suffix: {WELLKNOWN_SUFFIX}")
    print(f"Link relation:     {LINK_RELATION}")
    print("Specification:     https://agenticsystemcore.com")


if __name__ == "__main__":
    main()
