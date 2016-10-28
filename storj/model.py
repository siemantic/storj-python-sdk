# -*- coding: utf-8 -*-
"""Storj model module."""

import base64
import binascii
import hashlib
import os
import os.path
import random
import strict_rfc3339

from datetime import datetime
from steenzout.object import Object


class Bucket(Object):
    """Storage bucket.

    A bucket is a logical grouping of files
    which the user can assign permissions and limits to.

    Attributes:
        id (str): unique identifier.
        name (str): name.
        status (str): bucket status (Active, ...).
        user (str): user email address.
        created (:py:class:`datetime.datetime`):
            time when the bucket was created.
        storage (int): storage limit (in GB).
        transfer (int): transfer limit (in GB).
        pubkeys ():
    """

    def __init__(
            self, id=None, name=None, status=None, user=None,
            created=None, storage=None, transfer=None, pubkeys=None):
        self.id = id
        self.name = name
        self.status = status
        self.user = user
        self.storage = storage
        self.transfer = transfer
        self.pubkeys = pubkeys

        # self.files = FileManager(bucket_id=self.id)
        # self.pubkeys = BucketKeyManager(
        #     bucket=self, authorized_public_keys=self.pubkeys)
        # self.tokens = TokenManager(bucket_id=self.id)

        if created is not None:
            self.created = datetime.fromtimestamp(
                strict_rfc3339.rfc3339_to_timestamp(created))
        else:
            self.created = None

    def delete(self):
        BucketManager.delete(bucket_id=self.id)


class File(Object):
    """
    Attributes:
        bucket (): bucket unique identifier.
        hash ():
        mimetype ():
        filename ():
        size ():
        shardManager ():
    """

    def __init__(self, bucket=None, hash=None, mimetype=None,
                 filename=None, size=None, id=None):
        self.bucket = Bucket(id=bucket)
        self.hash = hash
        self.mimetype = mimetype
        self.filename = filename
        self.size = size
        self.shardManager = ShardManager()
        self.id = id

    @property
    def content_type(self):
        return self.mimetype

    @property
    def name(self):
        return self.filename

    def download(self):
        return api_client.file_download(bucket_id=self.bucket,
                                        file_hash=self.hash)

    def delete(self):
        bucket_files = FileManager(bucket_id=self.bucket)
        bucket_files.delete(self.id)


class Frame(Object):
    """File staging frame.

    Attributes:
        id (str): unique identifier.
        created (:py:class:`datetime.datetime`):
            time when the bucket was created.
        shards (list[:py:class:`Shard`]): shards that compose this frame.
    """

    def __init__(self, id=None, created=None, shards=None):
        self.id = id

        if created is not None:
            self.created = datetime.fromtimestamp(
                strict_rfc3339.rfc3339_to_timestamp(created))
        else:
            self.created = None

        if shards is None:
            self.shards = []
        else:
            self.shards = shards


class Keyring:

    def __init__(self):
        self.password = None
        self.salt = None

    def generate(self):
        user_pass = raw_input("Enter your keyring password: ")
        password = hex(random.getrandbits(512 * 8))[2:-1]
        salt = hex(random.getrandbits(32 * 8))[2:-1]

        pbkdf2 = hashlib.pbkdf2_hmac('sha512', password, salt, 25000, 512)

        key = hashlib.new('sha256', pbkdf2).hexdigest()
        IV = salt[:16]
        self.export_keyring(password, salt, user_pass)
        self.password = password
        self.salt = salt

    def export_keyring(self, password, salt, user_pass):
        plain = pad("{\"pass\" : \"%s\", \n\"salt\" : \"%s\"\n}"
                    % (password, salt))
        IV = hex(random.getrandbits(8 * 8))[2:-1]

        aes = AES.new(pad(user_pass), AES.MODE_CBC, IV)

        with open('key.b64', 'wb') as f:
            f.write(base64.b64encode(IV + aes.encrypt(plain)))

    def import_keyring(self, filepath):
        with open(filepath, 'rb') as f:
            keyb64 = f.read()

        user_pass = raw_input('Enter your keyring password: ')

        key_enc = base64.b64decode(keyb64)
        IV = key_enc[:16]
        key = AES.new(pad(user_pass), AES.MODE_CBC, IV)

        # returns the salt and password as a dict
        creds = eval(key.decrypt(key_enc[16:])[:-4])
        self.password = creds['pass']
        self.salt = creds['salt']
        return creds


class Shard:
    """Shard.

    Attributes:
        id (str): unique identifier.
        hash (str): hash of the data.
        size (long): size of the shard in bytes.
        index (int): numberic index of the shard in the frame.
        challenges (list[str]): list of challenge numbers
        tree (list[str]): audit merkle tree
        exclude (list[str]): list of farmer nodeIDs to exclude
    """

    def __init__(self, id=None, hash=None, size=None, index=None,
                 challenges=None, tree=None, exclude=None):
        self.id = id
        # self.path = None
        self.hash = hash
        self.size = size
        self.index = index
        self.challenges = challenges
        self.tree = tree
        self.exclude = exclude

        if challenges is not None:
            self.challenges = challenges
        else:
            self.challenges = []

        if tree is not None:
            self.tree = tree
        else:
            self.tree = []

        if exclude is not None:
            self.exclude = exclude
        else:
            self.exclude = []

    def all(self):
        return_string = 'Shard{index=%s, hash=%s, ' % (
            self.index,
            self.hash)
        return_string += 'size=%s, tree={%s}, challenges={%s}' % (
            self.size,
            ', '.join(self.tree),
            ', '.join(self.challenges))
        return return_string

    def add_challenge(self, challenge):
        """Append challenge.

        Args:
            challenge (str):.
        """
        self.challenges.append(challenge)

    def add_tree(self, tree):
        """Append tree."""
        self.tree.append(tree)

    def get_public_record(self):
        pass

    def get_private_record(self):
        pass


class ShardManager:
    """File shard manager.

    Attributes:
        filepath (str): path to the file.
        index (int): number of shards for the given file.
        nchallenges (int): number of challenges to be generated.
        shard_size (int/long): split file in chunks of this size.
        shards (list[:py:class:`Shard`]): list of shards
    """

    def __init__(self, filepath, shard_size, nchallenges=12):
        self.nchallenges = nchallenges
        self.shard_size = shard_size
        self.filepath = filepath

    @property
    def filepath(self):
        """"""
        return self._filepath

    @filepath.setter
    def filepath(self, value):
        if not isinstance(value, basestring):
            raise ValueError('%s must be a string' % value)
        elif not os.path.exists(value):
            raise ValueError('%s must exist' % value)
        elif not os.path.isfile(value):
            raise ValueError('%s must be a file' % value)

        self._filepath = value
        self.index = 0
        self._make_shards()

    def _make_shards(self):
        """Populates the shard manager with shards."""

        with open(self._filepath, 'rb') as fd:

            index = 0
            while True:
                chunk = fd.read(self.shard_size)

                if not chunk:
                    break

                challenges = self._make_challenges(self.nchallenges)

                shard = Shard(size=self.shard_size,
                              index=index,
                              hash=self._hash(chunk),
                              tree=self._make_tree(challenges, chunk),
                              challenges=challenges)

                self.shards.append(shard)
                index += 1

        self.index = len(self.shards)

    def _hash(self, data):
        """Returns ripemd160 of sha256 of a string as a string of hex"""
        data = data.encode('utf-8')
        data = bytes(data)
        output = binascii.hexlify(self._ripemd160(self._sha256(data)))
        return output.decode('utf-8')

    def _ripemd160(self, b):
        """Returns the ripemd160 digest of bytes as bytes"""
        return hashlib.new('ripemd160', b).digest()

    def _sha256(self, b):
        """Returns the sha256 digest of bytes as bytes"""
        return hashlib.new('sha256', b).digest()

    def _make_challenges(self, challenges=12):
        """Generates the challenge strings.

        Args:
            challenges (int): number of challenges to be generated.

        Returns:
            (list[str]): list of challenges.
        """
        return [self._make_challenge_string() for _ in xrange(challenges)]

    def _make_challenge_string(self):
        s = ''.join(os.urandom(32))
        return binascii.hexlify(s)

    def _make_tree(self, challenges, data):
        """
        Make a Storj MerkleTree built from the specified challeng

        Arguments:
        challenges (list[str]): A list of random challenges
        data (str): The data to be audited

        Returns:
        tree (MerkleTree): An audit tree from the specified

        """
        leaves = []
        for challenge in challenges:
            leaves.append['%s%s' % (challenge, data)]
        for leaf in leaves:
            leaf = self._hash(leaf)

        tree = MerkleTree(leaves)

        return tree


class Token(Object):
    """
    Attributes:
        token ():
        bucket ():
        operation ():
        expires ():
    """

    def __init__(self, token=None, bucket=None, operation=None, expires=None):
        self.id = token
        self.bucket_id = bucket
        self.operation = operation

        if expires is not None:
            self.expires = datetime.fromtimestamp(
                strict_rfc3339.rfc3339_to_timestamp(expires))
        else:
            self.expires = None


class MerkleTree:
    """
    Simple merkle hash tree. Nodes are stored as strings in rows.
    Row 0 is the root node, row 1 is its children, row 2 is their children, etc

    Arguments
    leaves (list[str]): leaves of the tree, as hex digests

    Attributes:
    leaves (list[str]): leaves of the tree, as hex digests
    depth (int): the number of levels in the tree
    count (int): the number of nodes in the tree
    rows (list[list[str]]): the levels of the tree
    """

    def __init__(self, leaves, prehashed=True):

        if not isinstance(leaves, list):
            raise ValueError("Leaves should be a list.")
        if len(leaves) < 1:
            raise ValueError("Leaves should contain at least one entry.")
        for leaf in leaves:
            if not isinstance(leaf, str):
                raise ValueError("Leaves should contain only strings.")

        self.leaves = [leaf for leaf in leaves]
        self.prehashed = prehashed
        self.depth = self._calculate_depth()
        self.count = 0
        self._rows = []

        self._generate()

    def _generate(self):
        """Generate the merkle tree from the leaves"""
        self._rows = [[] for _ in range(self.depth + 1)]

        if not self.prehashed:
            self.leaves = [self._hash(leaf) for leaf in self.leaves]

        # The number of leaves should be filled with hash of empty strings
        # until the number of leaves is a power of 2.
        # See https://storj.github.io/core/tutorial-protocol-spec.html
        while len(self.leaves) < (2 ** self.depth):
            self.leaves.append(self._hash(''))

        leaf_row = self.depth
        next_branches = self.depth - 1

        self._rows[leaf_row] = self.leaves
        if not self.prehashed:
            self.count += len(self.leaves)

        # Generate each row, starting from the bottom

        while next_branches >= 0:
            self._rows[next_branches] = self._make_row(next_branches)
            self.count += len(self._rows[next_branches])
            next_branches -= 1

    def _make_row(self, depth):
        """Generate the row at the specified depth"""
        row = []

        prior = self._rows[depth + 1]

        for i in range(0, len(prior), 2):
            entry = self._hash('%s%s' % (prior[i], prior[i + 1]))
            row.append(entry)

        return row

    def _hash(self, data):
        """Returns ripemd160 of sha256 of a string as a string of hex"""
        data = data.encode('utf-8')
        data = bytes(data)
        output = binascii.hexlify(self._ripemd160(self._sha256(data)))
        return output.decode('utf-8')

    def _ripemd160(self, b):
        """Returns the ripemd160 digest of bytes as bytes"""
        return hashlib.new('ripemd160', b).digest()

    def _sha256(self, b):
        """Returns the sha256 digest of bytes as bytes"""
        return hashlib.new('sha256', b).digest()

    def _calculate_depth(self):
        """Calculate the depth of the tree from the number of leaves"""
        pow = 0

        while (2 ** pow) < len(self.leaves):
            pow += 1

        return pow

    def get_root(self):
        """Return the root of the tree"""
        return self._rows[0][0]

    def get_level(self, depth):
        """Returns the tree row at the specified depth"""
        return self._rows[depth]
