import logging
from collections import defaultdict
from ordered_set import OrderedSet

from wake.testing import * # pyright: ignore reportMissingImports
from wake.testing.fuzzing import * # pyright: ignore reportMissingImports
from pytypes.tests.ERC1155Mock import ERC1155Mock


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ERC1155FuzzTest(FuzzTest):
    _erc1155: ERC1155Mock
    _balances: dict[Account, dict[uint256, uint256]]
    _approvals: dict[Account, OrderedSet[Account]]
    _token_ids: list[uint256]

    def pre_sequence(self):
        self._erc1155 = ERC1155Mock.deploy(True)
        self._balances = defaultdict(lambda: defaultdict(lambda: 0))
        self._approvals = defaultdict(lambda: OrderedSet([]))
        self._token_ids = [random_int(0, 2 ** 256 - 1, edge_values_prob=0.25) for _ in range(10)]

    @flow()
    def flow_mint(self, payload: bytes):
        minter = random_account()
        recipient = random_account()
        id = random.choice(self._token_ids)
        amount = random_int(0, 2 ** 256 - 1, edge_values_prob=0.05)

        with may_revert() as e:
            tx = self._erc1155.mint(recipient, id, amount, payload, from_=minter)

        if e.value == ERC1155Mock.AccountBalanceOverflow():
            assert self._balances[recipient][id] + amount >= 2 ** 256
            return "After Mint balance Exceeded"

        assert e.value is None
        assert self._balances[recipient][id] + amount < 2 ** 256
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(Address.ZERO, recipient.address, [id], [amount], payload),
            ERC1155Mock.TransferSingle(minter.address, Address.ZERO, recipient.address, id, amount),
            ERC1155Mock.AfterTokenTransfer(Address.ZERO, recipient.address, [id], [amount], payload),
        ]
        self._balances[recipient][id] += amount
        logger.info(f"Minted {amount} of {id} to {recipient}")

    @flow()
    def flow_batch_mint(self, payload: bytes):
        minter = random_account()
        recipient = random_account()
        ids = [random.choice(self._token_ids) for _ in range(random_int(0, 10, edge_values_prob=0.05))]
        amounts = [random_int(0, 2 ** 256 - 1, edge_values_prob=0.05) for _ in range(len(ids))]

        with may_revert() as e:
            tx = self._erc1155.batchMint(recipient, ids, amounts, payload, from_=minter)

        if e.value == ERC1155Mock.AccountBalanceOverflow():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[recipient][id] + amount >= 2 ** 256 for id, amount in amounts_by_ids.items())
            return "After Batch Mint balance Exceeded"

        assert e.value is None
        for id, amount in zip(ids, amounts):
            assert self._balances[recipient][id] + amount < 2 ** 256
            self._balances[recipient][id] += amount
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(Address.ZERO, recipient.address, ids, amounts, payload),
            ERC1155Mock.TransferBatch(minter.address, Address.ZERO, recipient.address, ids, amounts),
            ERC1155Mock.AfterTokenTransfer(Address.ZERO, recipient.address, ids, amounts, payload),
        ]
        logger.info(f"Minted {amounts} of {ids} to {recipient}")

    @flow()
    def flow_burn(self):
        owner = random_account()

        if random.random() < 0.8 and sum(self._balances[owner].values()) > 0:
            id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
        else:
            id = random.choice(self._token_ids)

        if self._balances[owner][id] == 0:
            amount = random.choice([0, 1])
        else:
            amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), min_prob=0.05, max_prob=0.01)

        operator = random.choices(
            chain.accounts,
            [0.5 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts]
        )[0]

        with may_revert() as e:
            tx = self._erc1155.burn(owner, id, amount, from_=operator)

        if e.value == ERC1155Mock.InsufficientBalance():
            assert self._balances[owner][id] - amount < 0
            return "After Burn Insufficient Balance"

        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator not in self._approvals[owner]
            return "After Burn Not Owner Nor Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, Address.ZERO, [id], [amount], bytes()),
            ERC1155Mock.TransferSingle(operator.address, owner.address, Address.ZERO, id, amount),
            ERC1155Mock.AfterTokenTransfer(owner.address, Address.ZERO, [id], [amount], bytes()),
        ]
        assert self._balances[owner][id] - amount >= 0
        self._balances[owner][id] -= amount

        assert operator == owner or operator in self._approvals[owner]

        logger.info(f"Burned {amount} of {id} from {owner}")


    @flow()
    def flow_burn_batch(self):
        owner = random_account()

        ids: list[uint256] = []
        amounts: list[uint256] = []
        for _ in range(random_int(0, 10, edge_values_prob=0.05)):
            if random.random() < 0.98 and sum(self._balances[owner].values()) > 0:
                id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
                ids.append(id)
                if self._balances[owner][id] == 0:
                    amount = random.choice([0, 1])
                else:
                    amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), edge_values_prob=0.05)
                amounts.append(amount)
            else:
                id = random.choice(self._token_ids)
                ids.append(id)
                amount = random_int(0, 2 ** 256 - 1, edge_values_prob=0.05)
                amounts.append(amount)

        operator = random.choices(
            chain.accounts,
            [0.5 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts]
        )[0]

        with may_revert() as e:
            tx = self._erc1155.batchBurn(owner, ids, amounts, from_=operator)

        if e.value == ERC1155Mock.InsufficientBalance():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] - amount < 0 for id, amount in amounts_by_ids.items())
            return "After Batch Burn Insufficient Balance"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"


        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, Address.ZERO, ids, amounts, bytes()),
            ERC1155Mock.TransferBatch(operator.address, owner.address, Address.ZERO, ids, amounts),
            ERC1155Mock.AfterTokenTransfer(owner.address, Address.ZERO, ids, amounts, bytes()),
        ]
        for id, amount in zip(ids, amounts):
            assert self._balances[owner][id] - amount >= 0
            self._balances[owner][id] -= amount

        assert operator == owner or operator in self._approvals[owner]
        logger.info(f"Burned {amounts} of {ids} from {owner}")


    @flow()
    def flow_burn_unchecked(self):
        owner = random_account()

        if random.random() < 0.8 and sum(self._balances[owner].values()) > 0:
            id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
        else:
            id = random.choice(self._token_ids)

        if self._balances[owner][id] == 0:
            amount = random.choice([0, 1])
        else:
            amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), min_prob=0.05, max_prob=0.01)

        operator = random.choices(
            chain.accounts + (Account(0), ),
            [0.25 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts] + [0.25]
        )[0]
        executor = random_account()

        with may_revert() as e:
            tx = self._erc1155.burnUnchecked(operator, owner, id, amount, from_=executor)

        if e.value == ERC1155Mock.InsufficientBalance():
            assert self._balances[owner][id] - amount < 0
            return "After Burn Insufficient Balance"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator != Account(0) and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, Address.ZERO, [id], [amount], bytes()),
            ERC1155Mock.TransferSingle(executor.address, owner.address, Address.ZERO, id, amount),
            ERC1155Mock.AfterTokenTransfer(owner.address, Address.ZERO, [id], [amount], bytes()),
        ]
        assert self._balances[owner][id] - amount >= 0
        self._balances[owner][id] -= amount

        assert operator == owner or operator == Account(0) or operator in self._approvals[owner]

        logger.info(f"Burned {amount} of {id} from {owner}")


    @flow()
    def flow_burn_batch_unchecked(self):
        owner = random_account()

        ids: list[uint256] = []
        amounts: list[uint256] = []
        for _ in range(random_int(0, 10, edge_values_prob=0.05)):
            if random.random() < 0.98 and sum(self._balances[owner].values()) > 0:
                id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
                ids.append(id)
                if self._balances[owner][id] == 0:
                    amount = random.choice([0, 1])
                else:
                    amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), edge_values_prob=0.05)
                amounts.append(amount)
            else:
                id = random.choice(self._token_ids)
                ids.append(id)
                amount = random_int(0, 2 ** 256 - 1, edge_values_prob=0.05)
                amounts.append(amount)

        operator = random.choices(
            chain.accounts + (Account(0), ),
            [0.25 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts] + [0.25]
        )[0]
        executor = random_account()

        with may_revert() as e:
            tx = self._erc1155.batchBurnUnchecked(operator, owner, ids, amounts, from_=executor)

        if e.value == ERC1155Mock.InsufficientBalance():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] - amount < 0 for id, amount in amounts_by_ids.items())
            return "After Batch Burn Insufficient Balance"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator != Account(0) and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, Address.ZERO, ids, amounts, bytes()),
            ERC1155Mock.TransferBatch(executor.address, owner.address, Address.ZERO, ids, amounts),
            ERC1155Mock.AfterTokenTransfer(owner.address, Address.ZERO, ids, amounts, bytes()),
        ]
        for id, amount in zip(ids, amounts):
            assert self._balances[owner][id] - amount >= 0
            self._balances[owner][id] -= amount

        assert operator == owner or operator == Account(0) or operator in self._approvals[owner]

        logger.info(f"Burned {amounts} of {ids} from {owner}")


    @flow()
    def flow_change_approval(self):
        a = random_account()
        operator = random_account()
        approval = operator in self._approvals[a]

        tx = self._erc1155.setApprovalForAll(operator, not approval, from_=a)
        assert tx.events == [
            ERC1155Mock.ApprovalForAll(a.address, operator.address, not approval),
        ]

        if approval:
            self._approvals[a].remove(operator)
        else:
            self._approvals[a].add(operator)

        logger.info(f"Changed approval of {operator} for {a} to {not approval}")

    @flow()
    def flow_change_approval_unchecked(self):
        owner = random_account()
        operator = random_account()
        executor = random_account()
        approval = operator in self._approvals[owner]

        tx = self._erc1155.setApprovalForAllUnchecked(owner, operator, not approval, from_=executor)
        assert tx.events == [
            ERC1155Mock.ApprovalForAll(owner.address, operator.address, not approval),
        ]

        if approval:
            self._approvals[owner].remove(operator)
        else:
            self._approvals[owner].add(operator)

        logger.info(f"Changed approval of {operator} for {owner} to {not approval}")

    @flow()
    def flow_safe_transfer(self, payload: bytes):
        owner = random_account()
        recipient = random_account()

        if random.random() < 0.8 and sum(self._balances[owner].values()) > 0:
            id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
        else:
            id = random.choice(self._token_ids)

        if self._balances[owner][id] == 0:
            amount = random.choice([0, 1])
        else:
            amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), min_prob=0.05, max_prob=0.01)

        operator = random.choices(
            chain.accounts,
            [0.5 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts]
        )[0]

        with may_revert() as e:
            tx = self._erc1155.safeTransferFrom(owner, recipient, id, amount, payload, from_=operator)

        if e.value == ERC1155Mock.InsufficientBalance():
            assert self._balances[owner][id] - amount < 0
            return "After Safe Transfer Insufficient Balance"
        if e.value == ERC1155Mock.AccountBalanceOverflow():
            assert self._balances[recipient][id] + amount > 2 ** 256 - 1
            return "After Safe Transfer Account Balance Overflow"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, recipient.address, [id], [amount], payload),
            ERC1155Mock.TransferSingle(operator.address, owner.address, recipient.address, id, amount),
            ERC1155Mock.AfterTokenTransfer(owner.address, recipient.address, [id], [amount], payload),
        ]
        assert self._balances[owner][id] - amount >= 0
        self._balances[owner][id] -= amount
        assert self._balances[recipient][id] + amount <= 2 ** 256 - 1
        self._balances[recipient][id] += amount

        assert operator == owner or operator in self._approvals[owner]

        logger.info(f"Transferred {amount} of {id} from {owner} to {recipient}")


    @flow()
    def flow_safe_batch_transfer(self, payload: bytes):
        owner = random_account()
        ids: list[uint256] = []
        amounts: list[uint256] = []
        for _ in range(random_int(0, 10, edge_values_prob=0.05)):
            if random.random() < 0.98 and sum(self._balances[owner].values()) > 0:
                id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
                ids.append(id)
                if self._balances[owner][id] == 0:
                    amount = random.choice([0, 1])
                else:
                    amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), edge_values_prob=0.05)
                amounts.append(amount)
            else:
                id = random.choice(self._token_ids)
                ids.append(id)
                amount = random_int(0, 2 ** 256 - 1, edge_values_prob=0.05)
                amounts.append(amount)

        operator = random.choices(
            chain.accounts,
            [0.5 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts]
        )[0]

        with may_revert() as e:
            tx = self._erc1155.safeBatchTransferFrom(owner, owner, ids, amounts, payload, from_=operator)

        if e.value == ERC1155Mock.InsufficientBalance():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] - amount < 0 for id, amount in amounts_by_ids.items())
            return "After Safe Batch Transfer Insufficient Balance"
        if e.value == ERC1155Mock.AccountBalanceOverflow():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] + amount > 2 ** 256 - 1 for id, amount in amounts_by_ids.items())
            return "After Safe Batch Transfer Account Balance Overflow"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, owner.address, ids, amounts, payload),
            ERC1155Mock.TransferBatch(operator.address, owner.address, owner.address, ids, amounts),
            ERC1155Mock.AfterTokenTransfer(owner.address, owner.address, ids, amounts, payload),
        ]
        for id, amount in zip(ids, amounts):
            assert self._balances[owner][id] - amount >= 0
            self._balances[owner][id] -= amount
            assert self._balances[owner][id] + amount <= 2 ** 256 - 1
            self._balances[owner][id] += amount

        assert operator == owner or operator in self._approvals[owner]
        logger.info(f"Transferred {amounts} of {ids} from {owner} to {owner}")


    @flow()
    def flow_safe_transfer_unchecked(self, payload: bytes):
        owner = random_account()
        recipient = random_account()

        if random.random() < 0.8 and sum(self._balances[owner].values()) > 0:
            id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
        else:
            id = random.choice(self._token_ids)

        if self._balances[owner][id] == 0:
            amount = random.choice([0, 1])
        else:
            amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), min_prob=0.05, max_prob=0.01)

        operator = random.choices(
            chain.accounts + (Account(0), ),
            [0.25 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts] + [0.25]
        )[0]
        executor = random_account()

        with may_revert() as e:
            tx = self._erc1155.safeTransferUnchecked(operator, owner, recipient, id, amount, payload, from_=executor)

        if e.value == ERC1155Mock.InsufficientBalance():
            assert self._balances[owner][id] - amount < 0
            return "After Safe Transfer Insufficient Balance"
        if e.value == ERC1155Mock.AccountBalanceOverflow():
            assert self._balances[recipient][id] + amount > 2 ** 256 - 1
            return "After Safe Transfer Account Balance Overflow"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator != Account(0) and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"


        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, recipient.address, [id], [amount], payload),
            ERC1155Mock.TransferSingle(executor.address, owner.address, recipient.address, id, amount),
            ERC1155Mock.AfterTokenTransfer(owner.address, recipient.address, [id], [amount], payload),
        ]
        assert self._balances[owner][id] - amount >= 0
        self._balances[owner][id] -= amount
        assert self._balances[recipient][id] + amount <= 2 ** 256 - 1
        self._balances[recipient][id] += amount

        assert operator == owner or operator == Account(0) or operator in self._approvals[owner]

        logger.info(f"Transferred {amount} of {id} from {owner} to {recipient}")



    @flow()
    def flow_safe_batch_transfer_unchecked(self, payload: bytes):
        owner = random_account()
        ids: list[uint256] = []
        amounts: list[uint256] = []
        for _ in range(random_int(0, 10, edge_values_prob=0.05)):
            if random.random() < 0.98 and sum(self._balances[owner].values()) > 0:
                id = random.choice([k for k in self._balances[owner].keys() if self._balances[owner][k] > 0])
                ids.append(id)
                if self._balances[owner][id] == 0:
                    amount = random.choice([0, 1])
                else:
                    amount = random_int(0, min(self._balances[owner][id] + 1, 2 ** 256 - 1), edge_values_prob=0.05)
                amounts.append(amount)
            else:
                id = random.choice(self._token_ids)
                ids.append(id)
                amount = random_int(0, 2 ** 256 - 1, edge_values_prob=0.05)
                amounts.append(amount)

        operator = random.choices(
            chain.accounts + (Account(0), ),
            [0.25 if a == owner else 0.5 / (len(chain.accounts) - 1) for a in chain.accounts] + [0.25]
        )[0]
        executor = random_account()

        with may_revert() as e:
            tx = self._erc1155.safeBatchTransferUnchecked(operator, owner, owner, ids, amounts, payload, from_=executor)


        if e.value == ERC1155Mock.InsufficientBalance():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] - amount < 0 for id, amount in amounts_by_ids.items())
            return "After Safe Batch Transfer Insufficient Balance"
        if e.value == ERC1155Mock.AccountBalanceOverflow():
            amounts_by_ids = defaultdict(int)
            for id, amount in zip(ids, amounts):
                amounts_by_ids[id] += amount
            assert any(self._balances[owner][id] + amount > 2 ** 256 - 1 for id, amount in amounts_by_ids.items())
            return "After Safe Batch Transfer Account Balance Overflow"
        if e.value == ERC1155Mock.NotOwnerNorApproved():
            assert operator != owner and operator != Account(0) and operator not in self._approvals[owner]
            return "Not Owner Of Token Or Not Approved"

        assert e.value is None
        assert tx.events == [
            ERC1155Mock.BeforeTokenTransfer(owner.address, owner.address, ids, amounts, payload),
            ERC1155Mock.TransferBatch(executor.address, owner.address, owner.address, ids, amounts),
            ERC1155Mock.AfterTokenTransfer(owner.address, owner.address, ids, amounts, payload),
        ]
        for id, amount in zip(ids, amounts):
            assert self._balances[owner][id] - amount >= 0
            self._balances[owner][id] -= amount
            assert self._balances[owner][id] + amount <= 2 ** 256 - 1
            self._balances[owner][id] += amount

        assert operator == owner or operator == Account(0) or operator in self._approvals[owner]

        logger.info(f"Transferred {amounts} of {ids} from {owner} to {owner}")

    @invariant(period=20)
    def invariant_balances(self) -> None:
        for a, balances in self._balances.items():
            assert self._erc1155.balanceOfBatch([a] * len(balances), list(balances.keys())) == list(balances.values())
            for id, balance in balances.items():
                assert self._erc1155.balanceOf(a, id) == balance

    @invariant(period=20)
    def invariant_approvals(self) -> None:
        for a in chain.accounts:
            for b in chain.accounts:
                assert self._erc1155.isApprovedForAll(a, b) == (b in self._approvals[a])


@chain.connect(accounts=20)
def test_erc1155_fuzz():
    ERC1155FuzzTest().run(1, 100)
