from dataclasses import dataclass, field

from wake.testing import *  # pyright: ignore reportMissingImports
from wake.testing.fuzzing import *  # pyright: ignore reportMissingImports

from pytypes.src.utils.ERC1967Factory import ERC1967Factory
from pytypes.tests.EIP712Mock import EIP712Mock


@dataclass
class Person(Struct):
    name: str
    wallet: Address


@dataclass
class Mail(Struct):
    from_: Person = field(metadata={"original_name": "from"})
    to: Person
    contents: str


class Eip712FuzzTest(FuzzTest):
    _proxy_factory: ERC1967Factory
    _eip712: EIP712Mock
    _eip712_proxy: EIP712Mock
    _signer: Account

    def __init__(self):
        self._proxy_factory = ERC1967Factory.deploy()

    def pre_sequence(self) -> None:
        self._eip712 = EIP712Mock.deploy()
        self._signer = Account.new()
        self._eip712_proxy = EIP712Mock(
            self._proxy_factory.deploy_(self._eip712, self._signer).return_value
        )


    @flow()
    def sign_flow(self, mail: Mail) -> None:

        mail_hash = keccak256(abi.encode_packed(
            keccak256(mail.encode_eip712_type().encode()),
            mail.encode_eip712_data()
        ))

        sign1 = self._signer.sign_hash(self._eip712.hashTypedData(mail_hash))
        sign2 = self._signer.sign_structured(mail, Eip712Domain(
            name=self._eip712.NAME(),
            version=self._eip712.VERSION(),
            chainId=chain.chain_id,
            verifyingContract=self._eip712.address,
        ))
        assert sign1 == sign2

        sign1 = self._signer.sign_hash(self._eip712_proxy.hashTypedData(mail_hash))
        sign2 = self._signer.sign_structured(mail, Eip712Domain(
            name=self._eip712_proxy.NAME(),
            version=self._eip712_proxy.VERSION(),
            chainId=chain.chain_id,
            verifyingContract=self._eip712_proxy.address,
        ))
        assert sign1 == sign2


@chain.connect()
def test_eip712_fuzz():
    Eip712FuzzTest().run(10, 10000)
