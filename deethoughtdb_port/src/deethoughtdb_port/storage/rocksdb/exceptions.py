class RocksDBPortError(RuntimeError):
    pass


class RocksDBBindingUnavailable(RocksDBPortError):
    pass
