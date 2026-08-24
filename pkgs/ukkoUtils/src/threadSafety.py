###########################################################################################
#

import threading
from typing import Generic, TypeVar

ObjType = TypeVar("ObjType")

###########################################################################################
#


class ThreadSafe(Generic[ObjType]):
    """Protect an object with a recursive lock (RLock).  eg:
    ```
    locked = ThreadSafe[list](['a', 'b', 'c'])

    def in_thread_1():
        with locked as my_list:
            if len(my_list) > 0:
                my_list.pop()

    def in_thread_2():
        with locked as my_list:
            my_list.append('Fred')
    ```

        The protected object is only reachable inside a `with` block, which
        holds the lock for the duration of the block and releases it
        automatically -- even if the block raises.
        This wrapper makes it easy to have thread-safe code.
        However you can always hack bypasses around it - such as stashing
        the object returned by `with` in a variable that outlives the block
        Don't do this.
    """

    def __init__(self, protectThis: ObjType):
        self._lock = threading.RLock()
        self._protectedObject: ObjType = protectThis

    def acquire(self, blocking=True, timeout=-1) -> bool:
        return self._lock.acquire(blocking, timeout)

    def release(self):
        self._lock.release()

    def __enter__(self) -> ObjType:
        self._lock.__enter__()
        return self._protectedObject

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._lock.__exit__(exc_type, exc_val, exc_tb)


#
###########################################################################################
