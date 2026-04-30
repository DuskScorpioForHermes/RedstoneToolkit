from enum import StrEnum, auto
from pathlib import Path
from github import Github, Auth # noqa
from semantic_version import Version
from functools import cache

import os
import re
import json
import tomllib


class PlatForm(StrEnum):
    MODRINTH = auto()
    CURSEFORGE = auto()


class DataType(StrEnum):
    MC_VERS = auto()
    DIR_MAP = auto()
    TYPE_MAP = auto()
    VER_MAP = auto()
    PUBLISH = auto()

    CREATE = auto()
    SHOULD_CREATE = auto()


class Matrix:
    def __init__(self):
        self.token: str | None = os.getenv("GH_TOKEN")
        self.repository: str = os.getenv("GITHUB_REPOSITORY", "DuskScorpio/RedstoneToolkit")

        self.data = {
            DataType.CREATE: list(),
            DataType.SHOULD_CREATE: False,

            PlatForm.MODRINTH: {
                DataType.MC_VERS: list(),
                DataType.DIR_MAP: dict(),
                DataType.TYPE_MAP: dict(),
                DataType.VER_MAP: dict(),
                DataType.PUBLISH: False
            },

            PlatForm.CURSEFORGE: {
                DataType.MC_VERS: list(),
                DataType.DIR_MAP: dict(),
                DataType.TYPE_MAP: dict(),
                DataType.VER_MAP: dict(),
                DataType.PUBLISH: False
            }
        }

    @staticmethod
    def is_beta(ver: str) -> bool:
        return bool(Version.coerce(ver).prerelease)

    def run(self):
        for platform in PlatForm:
            dirs = [i.name for i in Path(platform).iterdir() if i.joinpath("pack.toml").exists()]
            for mc_dir in dirs:
                self.write_data(platform, mc_dir)

            # It is set to true only when there is a version
            if self.data[platform][DataType.MC_VERS]:
                self.data[platform][DataType.PUBLISH] = True

        # Set to true when there is a tag that needs to be created
        if self.data[DataType.CREATE]:
            self.data[DataType.SHOULD_CREATE] = True

        self.output_json()

    def write_data(self, platform: PlatForm, mc_dir: str):
        path = Path(platform).joinpath(mc_dir).joinpath("pack.toml")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        mc_ver: str = data["versions"]["minecraft"]
        pack_ver: str = data["version"]
        pack_name: str = data["name"]

        # There should be no alpha version
        if re.match(".*alpha\\.\\d+", pack_ver): raise ValueError

        # skip the cf snapshot version release
        if platform == PlatForm.CURSEFORGE and self.is_beta(mc_ver): return

        # If it has already been published, don't publish it again
        end = "mrpack" if platform == PlatForm.MODRINTH else "zip"
        file_name = f"{pack_name}-{pack_ver}+mc{mc_ver}.{end}"
        if file_name in self.get_assets(pack_ver): return

        # If the tag doesn't exist, we need to have it pre-created
        if not self.tag_exists(pack_ver) and not pack_ver in self.data[DataType.CREATE]:
            self.data[DataType.CREATE].append(pack_ver)

        # write data
        self.data[platform][DataType.MC_VERS].append(mc_ver)
        self.data[platform][DataType.DIR_MAP][mc_ver] = mc_dir
        self.data[platform][DataType.TYPE_MAP][mc_ver] = "beta" if self.is_beta(pack_ver) else "release"
        self.data[platform][DataType.VER_MAP][mc_ver] = pack_ver

    def output_json(self):
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f)

    def tag_exists(self, ver: str) -> bool:
        return f"release/{ver}" in self.read_tags()


    def get_auth(self) -> Auth.Token | None:
        if self.token is None:
            return None
        else:
            return Auth.Token(self.token)

    @cache
    def read_tags(self) -> list[str]:
        with Github(auth=self.get_auth()) as g:
            repo = g.get_repo(self.repository)
            return [i.tag_name for i in repo.get_releases()]

    @cache
    def get_assets(self, ver: str) -> list[str]:
        if not self.tag_exists(ver):
            return list()
        else:
            tag = f"release/{ver}"
            with Github(auth=self.get_auth()) as g:
                repo = g.get_repo(self.repository)
                return [i.name for i in repo.get_release(tag).get_assets()]


if __name__ == "__main__":
    Matrix().run()
