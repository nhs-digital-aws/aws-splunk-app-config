__author__ = 'pj'

from esapi.reference.default_encoder import DefaultEncoder
from exception import IntrusionException

class SecurityEncoder(DefaultEncoder):

    def canonicalize(self, input_):
        """
        Canonicalization is to reduce a possibly encoded string down to its
        simplest form. It is the effective way to avoid attack.
        """
        if input_ is None:
            return None

        working = input_[:]
        codecs_found = []
        found_count = 0
        clean = False

        while not clean:
            clean = True
            # Try each codec and keep track of which ones work
            for codec in self.codecs:
                old = working[:]
                working = codec.decode(working)
                if old != working:
                    if codec.__class__.__name__ not in codecs_found:
                        codecs_found.append(codec.__class__.__name__)
                    if clean:
                        found_count += 1
                    clean = False

        if found_count >= 2 and len(codecs_found) > 1:
            raise IntrusionException("Multiple (%d) and mixed encoding (%s) detected in (%s)" % (found_count, str(codecs_found), input_))

        elif found_count >= 2:
            raise IntrusionException("Multiple (%d) encoding detected in (%s)" % (found_count, input_) )

        elif len(codecs_found) > 1:
            raise IntrusionException("Mixed encoding (%s) detected in (%s)" % (str(codecs_found), input_))

        return working
