from typing import List, Optional, Any, TypeVar, Type
from xo.jsonrpc import JsonRpc

from abc import ABC
import asyncio
import secrets
import string

class XO:
    def __init__(self, url: str, user: str, password: str):
        self.connection = JsonRpc('ws://%s/api/' % url)
        self.user = user
        self.password = password

    async def send(self, method: str, params: dict = {}):
        return await self.connection.send(method, params)

    async def open(self):
        await self.connection.connect()
        await self.send("session.signIn", { "email": self.user, "password": self.password})

    async def close(self):
        await self.connection.close()

    async def find_template(self, name: str) -> List[str]:
        templates = await self.send("xo.getAllObjects", {"filter": { "type": "VM-template", "name_label": name }})
        return list(templates.keys())

    async def list_commands(self):
        methods = await self.send("system.getMethodsInfo")
        for name, data in methods.items():
            print("")
            print(name)
            if "params" in data and data["params"] != {}:
                print("    ", end = "")
                for param, info in data["params"].items():
                    optional = "optional" in info and info["optional"]
                    if optional:
                        print("[", end="")

                    print(param + "=", end="")
                    if "type" in info:
                        if isinstance(info["type"], list):
                            print("<" + "|".join(info["type"]) + ">", end="")
                        else:
                            print("<" + info["type"] + ">", end="")
                    if optional:
                        print("]", end="")
                    print(" ", end = "")
                print("")
            try:
                print("    " + data["description"])
            except KeyError:
                pass

T = TypeVar('T', bound='XOObject')

class XOObject(ABC):
    TYPE = ""

    def __init__(self, xo: XO, id_: str):
        self.xo = xo
        self.id_ = id_

    @classmethod
    async def from_name(cls: Type[T], xo: XO, name: str) -> List[T]:
        response = await xo.send("xo.getAllObjects", { "filter": { "type": cls.TYPE, "name_label": name }})
        return [cls(xo, id_) for id_ in response]

    async def get_info(self) -> dict:
        responses = await self.xo.send("xo.getAllObjects", { "filter": { "type": self.TYPE }})
        return responses[self.id_]

class Disk(XOObject):
    TYPE = "VDI"

class SR(XOObject):
    TYPE = "SR"

    async def new_disk(self, name: str, size: str):
        id_ = await self.xo.send("disk.create", {
            "name": name,
            "sr": self.id_,
            "size": size
        })
        return Disk(self.xo, id_)

class VM(XOObject):
    type = "VM"

    @staticmethod
    async def new(xo: XO, name: str, template: str) -> 'VM':
        templates = await xo.find_template(template)
        if len(templates) != 1:
            raise ValueError("There must be exaclty one template with given name")

        vmid = await xo.send("vm.create", {
            "template": templates[0],
            "name_label": name,
        })

        return VM(xo, vmid)

    async def set_properties(self, **kwargs):
        kwargs["id"] = self.id_
        await self.xo.send("vm.set", kwargs)
    
    async def set_cores(self, cores: int):
        await self.set_properties(CPUs=cores, coresPerSocket=cores)

    async def set_memory(self, memory: str):
        await self.set_properties(memory=memory)

    async def set_description(self, description: str):
        await self.set_properties(name_description=description)

    async def add_disk(self, disk: Disk):
        await self.xo.send("vm.attachDisk", {
            "vdi": disk.id_,
            "vm": self.id_
        })

class User:
    def __init__(self, xo: XO, uid: str):
        self.xo = xo
        self.id_ = uid

    @staticmethod
    async def new(xo: XO, name: str, admin: bool = False, password: Optional[str] = None) -> 'User':
        if password is None:
            letters = string.ascii_lowercase
            password = ''.join(secrets.choice(letters) for i in range(30))

        uid = await xo.send('user.create', {
            "email": name,
            "password": password,
            "permission": "admin" if admin else "none"
        })

        return User(xo, uid)

    @staticmethod
    async def from_name(xo: XO, name: str) -> Optional['User']:
        for user in await xo.send("user.getAll"):
            if user["email"] == name:
                return User(xo, user["id"])

        return None

    async def get_info(self) -> dict:
        for user in await self.xo.send("user.getAll"):
            if user["id"] == self.id_:
                return user

        raise ValueError

    async def delete(self):
        await self.xo.send("user.delete", { "id": self.id_ })

    async def clear_acl(self, target: XOObject):
        current = await self.xo.send("acl.get")

        waits = set()
        for line in current:
            if line["subject"] == self.id_ and line["object"] == target.id_:
                del line["id"]
                waits.add(self.xo.send("acl.remove", line))

        if waits != set():
            await asyncio.wait(waits)

    async def set_acl(self, target: XOObject, access: str):
        await self.clear_acl(target)

        await self.xo.send("acl.add", {
            "subject": self.id_,
            "object": target.id_,
            "action": access
        })
