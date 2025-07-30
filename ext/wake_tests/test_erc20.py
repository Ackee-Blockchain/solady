from wake.testing import * # pyright: ignore reportMissingImports

from pytypes.ext.wake_tests.helpers.ERC20Mock import ERC20Mock
from pytypes.ext.wake_tests.helpers.NoETHMock import NoETHMock
from pytypes.ext.wake_tests.weird.Approval import ApprovalRaceToken
from pytypes.ext.wake_tests.weird.ApprovalToZero import ApprovalToZeroToken
from pytypes.ext.wake_tests.weird.BlockList import BlockableToken
from pytypes.ext.wake_tests.weird.HighDecimals import HighDecimalToken
from pytypes.ext.wake_tests.weird.Bytes32Metadata import ERC20 as Bytes32MetadataToken
from pytypes.ext.wake_tests.weird.MissingReturns import MissingReturnToken
from pytypes.ext.wake_tests.weird.NoRevert import NoRevertToken
from pytypes.ext.wake_tests.weird.Pausable import PausableToken
from pytypes.ext.wake_tests.weird.Proxied import ProxiedToken, TokenProxy
from pytypes.ext.wake_tests.weird.Reentrant import ReentrantToken
from pytypes.ext.wake_tests.weird.ReturnsFalse import ReturnsFalseToken
from pytypes.ext.wake_tests.weird.TransferFee import TransferFeeToken
from pytypes.ext.wake_tests.weird.Uint96 import Uint96ERC20
from pytypes.ext.wake_tests.weird.Upgradable import Proxy as UpgradableToken

from pytypes.src.utils.SafeTransferLib import SafeTransferLib


@chain.connect()
def test_erc20():
    milady = chain.accounts[0]
    accountoor = chain.accounts[1]
    chain.set_default_accounts(milady)

    tokenoor = ERC20Mock.deploy("Mockoor", "MOCK", 18)

    tokenoor.mint(milady, 2**30)
    assert tokenoor.balanceOf(milady) == 2**30

    tokenoor.approve(accountoor, 2**30)
    assert tokenoor.allowance(milady, accountoor) == 2**30

    tokenoor.transferFrom(milady, accountoor, 2**30, from_=accountoor)
    assert tokenoor.allowance(milady, accountoor) == 0

    assert tokenoor.balanceOf(milady) == 0
    assert tokenoor.balanceOf(accountoor) == 2**30

@chain.connect()
def test_safe_transfer_eth():
    milady = chain.accounts[0]
    accountoor = chain.accounts[1]
    chain.set_default_accounts(milady)

    SafeTransferLib.deploy()

    tokenoor = ERC20Mock.deploy("Mockoor", "MOCK", 18)
    tokenoor.balance = 5000
    accountoor.balance = 0

    # should change balance
    tokenoor.safeTransferETH(accountoor, 1000)
    assert tokenoor.balance == 4000
    assert accountoor.balance == 1000

    noeth = NoETHMock.deploy()

    # should revert
    with must_revert():
        tokenoor.safeTransferETH(noeth, 1000)

    # should change balance
    tokenoor.forceSafeTransferETH(noeth, 1000)
    assert tokenoor.balance == 3000
    assert noeth.balance == 1000

    # should force on bad gas stipend
    tokenoor.forceSafeTransferETHGas(accountoor, 1000, 0)
    assert tokenoor.balance == 2000
    assert accountoor.balance == 2000

    # should change balance
    tokenoor.trySafeTransferETH(accountoor, 1000, 0)
    assert tokenoor.balance == 1000
    assert accountoor.balance == 3000

    # should not revert
    tokenoor.trySafeTransferETH(noeth, 1000, 0)
    assert tokenoor.balance == 1000
    assert noeth.balance == 1000

@chain.connect()
def test_safe_transfer():
    milady = chain.accounts[0]
    chain.set_default_accounts(milady)

    SafeTransferLib.deploy()

    tokenoor = ERC20Mock.deploy("Mockoor", "MOCK", 18)
    tokenoor.mint(tokenoor, 2**30)

    tokenoor.safeTransfer(tokenoor, milady, 2**30)
    assert tokenoor.balanceOf(milady) == 2**30
    assert tokenoor.balanceOf(tokenoor) == 0

    tokenoor.approve(tokenoor, 2**30)
    assert tokenoor.allowance(milady, tokenoor) == 2**30
    tokenoor.safeTransferFrom(tokenoor, milady, tokenoor, 2**30)
    assert tokenoor.balanceOf(milady) == 0
    assert tokenoor.balanceOf(tokenoor) == 2**30

    tokenoor.mint(tokenoor, 2**30)
    tokenoor.safeTransferAll(tokenoor, milady)
    assert tokenoor.balanceOf(milady) == 2**30 * 2
    assert tokenoor.balanceOf(tokenoor) == 0

    # test safe balanceOf
    assert tokenoor.balanceOfoor(milady, milady) == 0
    assert tokenoor.balanceOfoor(tokenoor, milady) == 2**30 * 2

def safe_transfer_weird(weird: Account):
    milady = chain.accounts[0]
    weird = ERC20Mock(weird)

    SafeTransferLib.deploy()

    tokenoor = ERC20Mock.deploy("Mockoor", "MOCK", 18)

    weird.mint(tokenoor, 2**30)
    tokenoor.safeTransfer(weird, milady, 2**30)
    assert weird.balanceOf(milady) == 2**30
    assert weird.balanceOf(tokenoor) == 0

    weird.mint(tokenoor, 2**30)
    tokenoor.safeTransferAll(weird, milady)
    assert weird.balanceOf(milady) == 2**30 * 2
    assert weird.balanceOf(tokenoor) == 0

    weird.mint(tokenoor, 2**30)
    tokenoor.safeTransferFrom(weird, tokenoor, milady, 2**30)
    assert weird.balanceOf(milady) == 2**30 * 3
    assert weird.balanceOf(tokenoor) == 0

    weird.approve(tokenoor, 2**30)
    assert weird.allowance(milady, tokenoor) == 2**30
    tokenoor.safeTransferFrom(weird, milady, tokenoor, 2**30)
    assert weird.balanceOf(milady) == 2**30 * 2
    assert weird.balanceOf(tokenoor) == 2**30

    # test safe balanceOf
    assert tokenoor.balanceOfoor(milady, milady) == 0
    assert tokenoor.balanceOfoor(weird, milady) == 2**30 * 2

@chain.connect()
def test_safe_transfer_weird_1():
    weird = ApprovalRaceToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_2():
    weird = ApprovalToZeroToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_3():
    weird = BlockableToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_4():
    weird = HighDecimalToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_5():
    weird = Bytes32MetadataToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_6():
    weird = MissingReturnToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_7():
    weird = NoRevertToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_8():
    weird = PausableToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_9():
    impl = ProxiedToken.deploy(0)
    weird_proxy = TokenProxy.deploy(impl)
    weird = ProxiedToken(weird_proxy)
    weird.setDelegator(weird_proxy, True)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_10():
    weird = ReturnsFalseToken.deploy(0)
    with must_revert():
        safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_11():
    weird = ReentrantToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_12():
    weird = TransferFeeToken.deploy(0,0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_13():
    weird = Uint96ERC20.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_safe_transfer_weird_14():
    weird = UpgradableToken.deploy(0)
    safe_transfer_weird(weird)

@chain.connect()
def test_mint_to_zero_address():
    tokenoor = ERC20Mock.deploy("Mockoor", "MOCK", 18)
    tokenoor.mint(Address(0), 2**256-1)
    assert tokenoor.balanceOf(Address(0)) == 2**256-1
