import math
from math import trunc
import pytest

from hypothesis import given, assume
from hypothesis.errors import UnsatisfiedAssumption
from hypothesis.strategies import integers, floats, one_of, just

from segpy.ibm_float import (ieee2ibm, ibm2ieee, MAX_IBM_FLOAT, SMALLEST_POSITIVE_NORMAL_IBM_FLOAT,
                             LARGEST_NEGATIVE_NORMAL_IBM_FLOAT, MIN_IBM_FLOAT, IBMFloat, EPSILON_IBM_FLOAT,
                             MAX_EXACT_INTEGER_IBM_FLOAT, MIN_EXACT_INTEGER_IBM_FLOAT, EXPONENT_BIAS)

from segpy.util import almost_equal

ibm_compatible_negative_floats = floats(MIN_IBM_FLOAT, LARGEST_NEGATIVE_NORMAL_IBM_FLOAT)
ibm_compatible_positive_floats = floats(SMALLEST_POSITIVE_NORMAL_IBM_FLOAT, MAX_IBM_FLOAT)

ibm_compatible_non_negative_floats = one_of(
    just(0.0),
    floats(SMALLEST_POSITIVE_NORMAL_IBM_FLOAT, MAX_IBM_FLOAT))

ibm_compatible_non_positive_floats = one_of(
    just(0.0),
    floats(MIN_IBM_FLOAT, LARGEST_NEGATIVE_NORMAL_IBM_FLOAT))


def ibm_compatible_floats(min_f, max_f):
    truncated_min_f = max(min_f, MIN_IBM_FLOAT)
    truncated_max_f = min(max_f, MAX_IBM_FLOAT)

    strategies = []
    if truncated_min_f <= LARGEST_NEGATIVE_NORMAL_IBM_FLOAT <= truncated_max_f:
        strategies.append(floats(truncated_min_f, LARGEST_NEGATIVE_NORMAL_IBM_FLOAT))

    if truncated_min_f <= SMALLEST_POSITIVE_NORMAL_IBM_FLOAT <= truncated_max_f:
        strategies.append(floats(SMALLEST_POSITIVE_NORMAL_IBM_FLOAT, truncated_max_f))

    if truncated_min_f <= 0 <= truncated_max_f:
        strategies.append(just(0.0))

    if len(strategies) == 0:
        strategies.append(floats(truncated_min_f, truncated_max_f))

    return one_of(*strategies)


any_ibm_compatible_floats = ibm_compatible_floats(MIN_IBM_FLOAT, MAX_IBM_FLOAT)


class TestIbm2Ieee:

    @given(integers(0, 255))
    def test_zero(self, a):
        assert ibm2ieee(bytes([a, 0, 0, 0])) == 0.0

    def test_positive_half(self):
        assert ibm2ieee(bytes((0b11000000, 0x80, 0x00, 0x00))) == -0.5

    def test_negative_half(self):
        assert ibm2ieee(bytes((0b01000000, 0x80, 0x00, 0x00))) == 0.5

    def test_one(self):
        assert ibm2ieee(b'\x41\x10\x00\x00') == 1.0

    def test_negative_118_625(self):
        # Example taken from Wikipedia http://en.wikipedia.org/wiki/IBM_Floating_Point_Architecture
        assert ibm2ieee(bytes((0b11000010, 0b01110110, 0b10100000, 0b00000000))) == -118.625

    def test_largest_representable_number(self):
        assert ibm2ieee(bytes((0b01111111, 0b11111111, 0b11111111, 0b11111111))) == MAX_IBM_FLOAT

    def test_smallest_positive_normalised_number(self):
        assert ibm2ieee(bytes((0b00000000, 0b00010000, 0b00000000, 0b00000000))) == SMALLEST_POSITIVE_NORMAL_IBM_FLOAT

    def test_largest_negative_normalised_number(self):
        assert ibm2ieee(bytes((0b10000000, 0b00010000, 0b00000000, 0b00000000))) == LARGEST_NEGATIVE_NORMAL_IBM_FLOAT

    def test_smallest_representable_number(self):
        assert ibm2ieee(bytes((0b11111111, 0b11111111, 0b11111111, 0b11111111))) == MIN_IBM_FLOAT

    def test_error_1(self):
        assert ibm2ieee(bytes((196, 74, 194, 143))) == -19138.55859375

    def test_error_2(self):
        assert ibm2ieee(bytes((191, 128, 0, 0))) == -0.03125

    def test_subnormal(self):
        assert ibm2ieee(bytes((0x00, 0x00, 0x00, 0x20))) == 1.6472184286297693e-83

    def test_subnormal_is_subnormal(self):
        assert 0 < ibm2ieee(bytes((0x00, 0x00, 0x00, 0x20))) < SMALLEST_POSITIVE_NORMAL_IBM_FLOAT

    def test_subnormal_smallest_subnormal(self):
        assert ibm2ieee(bytes((0x00, 0x00, 0x00, 0x01))) == 5.147557589468029e-85


class TestIeee2Ibm:

    def test_zero(self):
        assert ieee2ibm(0.0) == b'\0\0\0\0'

    def test_positive_half(self):
        assert ieee2ibm(-0.5) == bytes((0b11000000, 0x80, 0x00, 0x00))

    def test_negative_half(self):
        assert ieee2ibm(0.5) == bytes((0b01000000, 0x80, 0x00, 0x00))

    def test_one(self):
        assert ieee2ibm(1.0) == b'\x41\x10\x00\x00'

    def test_negative_118_625(self):
        # Example taken from Wikipedia http://en.wikipedia.org/wiki/IBM_Floating_Point_Architecture
        assert ieee2ibm(-118.625) == bytes((0b11000010, 0b01110110, 0b10100000, 0b00000000))

    def test_0_1(self):
        # Note, this is different from the Wikipedia example, because the Wikipedia example does
        # round to nearest, and our routine does round to zero
        assert ieee2ibm(0.1) == bytes((0b01000000, 0b00011001, 0b10011001, 0b10011001))

    def test_subnormal(self):
        assert ieee2ibm(1.6472184286297693e-83) == bytes((0x00, 0x00, 0x00, 0x20))

    def test_smallest_subnormal(self):
        assert ieee2ibm(5.147557589468029e-85) == bytes((0x00, 0x00, 0x00, 0x01))

    def test_too_small_subnormal(self):
        with pytest.raises(FloatingPointError):
            ieee2ibm(1e-86)

    def test_nan(self):
        with pytest.raises(ValueError):
            ieee2ibm(float('nan'))

    def test_inf(self):
        with pytest.raises(ValueError):
            ieee2ibm(float('inf'))

    def test_too_large(self):
        with pytest.raises(OverflowError):
            ieee2ibm(MAX_IBM_FLOAT * 10)

    def test_too_small(self):
        with pytest.raises(OverflowError):
            ieee2ibm(MIN_IBM_FLOAT * 10)


class TestIbm2IeeeRoundtrip:

    def test_zero(self):
        ibm_start = b'\0\0\0\0'
        f = ibm2ieee(ibm_start)
        ibm_result = ieee2ibm(f)
        assert ibm_start == ibm_result

    def test_positive_half(self):
        ibm_start = bytes((0b11000000, 0x80, 0x00, 0x00))
        f = ibm2ieee(ibm_start)
        ibm_result = ieee2ibm(f)
        assert ibm_start == ibm_result

    def test_negative_half(self):
        ibm_start = bytes((0b01000000, 0x80, 0x00, 0x00))
        f = ibm2ieee(ibm_start)
        ibm_result = ieee2ibm(f)
        assert ibm_start == ibm_result

    def test_one(self):
        ibm_start = b'\x41\x10\x00\x00'
        f = ibm2ieee(ibm_start)
        ibm_result = ieee2ibm(f)
        assert ibm_start == ibm_result

    def test_subnormal(self):
        ibm_start = bytes((0x00, 0x00, 0x00, 0x20))
        f = ibm2ieee(ibm_start)
        ibm_result = ieee2ibm(f)
        assert ibm_start == ibm_result


class TestIBMFloat:

    def test_zero_from_float(self):
        zero = IBMFloat.from_float(0.0)
        assert zero.is_zero()

    def test_zero_from_bytes(self):
        zero = IBMFloat.from_bytes(b'\x00\x00\x00\x00')
        assert zero.is_zero()

    def test_subnormal(self):
        ibm = IBMFloat.from_float(1.6472184286297693e-83)
        assert ibm.is_subnormal()

    def test_smallest_subnormal(self):
        ibm = IBMFloat.from_float(5.147557589468029e-85)
        assert bytes(ibm) == bytes((0x00, 0x00, 0x00, 0x01))

    def test_too_small_subnormal(self):
        with pytest.raises(FloatingPointError):
            IBMFloat.from_float(1e-86)

    def test_nan(self):
        with pytest.raises(ValueError):
            IBMFloat.from_float(float('nan'))

    def test_inf(self):
        with pytest.raises(ValueError):
            IBMFloat.from_float(float('inf'))

    def test_too_large(self):
        with pytest.raises(OverflowError):
            IBMFloat.from_float(MAX_IBM_FLOAT * 10)

    def test_too_small(self):
        with pytest.raises(OverflowError):
            IBMFloat.from_float(MIN_IBM_FLOAT * 10)

    @given(any_ibm_compatible_floats)
    def test_bool(self, f):
        assert bool(IBMFloat.from_float(f)) == bool(f)

    @given(integers(0, 255),
           integers(0, 255),
           integers(0, 255),
           integers(0, 255))
    def test_bytes_roundtrip(self, a, b, c, d):
        b = bytes((a, b, c, d))
        ibm = IBMFloat.from_bytes(b)
        assert bytes(ibm) == b

    @given(any_ibm_compatible_floats)
    def test_floats_roundtrip(self, f):
        ibm = IBMFloat.from_float(f)
        assert almost_equal(f, float(ibm), epsilon=EPSILON_IBM_FLOAT)

    @given(integers(0, MAX_EXACT_INTEGER_IBM_FLOAT - 1),
           ibm_compatible_floats(0.0, 1.0))
    def test_trunc_above_zero(self, i, f):
        assume(f != 1.0)
        ieee = i + f
        ibm = IBMFloat.from_float(ieee)
        assert trunc(ibm) == i

    @given(integers(MIN_EXACT_INTEGER_IBM_FLOAT + 1, 0),
           ibm_compatible_floats(0.0, 1.0))
    def test_trunc_below_zero(self, i, f):
        assume(f != 1.0)
        ieee = i - f
        ibm = IBMFloat.from_float(ieee)
        assert trunc(ibm) == i

    @given(integers(MIN_EXACT_INTEGER_IBM_FLOAT, MAX_EXACT_INTEGER_IBM_FLOAT - 1),
           ibm_compatible_floats(EPSILON_IBM_FLOAT, 1 - EPSILON_IBM_FLOAT))
    def test_ceil(self, i, f):
        ieee = i + f
        ibm = IBMFloat.from_float(ieee)
        assert math.ceil(ibm) == i + 1

    @given(integers(MIN_EXACT_INTEGER_IBM_FLOAT, MAX_EXACT_INTEGER_IBM_FLOAT - 1),
           ibm_compatible_floats(EPSILON_IBM_FLOAT, 1 - EPSILON_IBM_FLOAT))
    def test_floor(self, i, f):
        ieee = i + f
        ibm = IBMFloat.from_float(ieee)
        assert math.floor(ibm) == i

    def test_normalise_subnormal_expect_failure(self):
        # This float has an base-16 exponent of -64 (the minimum) and cannot be normalised
        ibm = IBMFloat.from_float(1.6472184286297693e-83)
        assert ibm.is_subnormal()
        with pytest.raises(FloatingPointError):
            ibm.normalize()

    def test_normalise_subnormal1(self):
        ibm = IBMFloat.from_bytes((0b01000000, 0b00000000, 0b11111111, 0b00000000))
        assert ibm.is_subnormal()
        normalized = ibm.normalize()
        assert not normalized.is_subnormal()

    def test_normalise_subnormal2(self):
        ibm = IBMFloat.from_bytes((64, 1, 0, 0))
        assert ibm.is_subnormal()
        normalized = ibm.normalize()
        assert not normalized.is_subnormal()

    @given(integers(128, 255),
           integers(0, 255),
           integers(0, 255),
           integers(4, 23))
    def test_normalise_subnormal(self, b, c, d, shift):
        mantissa = (b << 16) | (c << 8) | d
        assume(mantissa != 0)
        mantissa >>= shift
        assert mantissa != 0

        sa = EXPONENT_BIAS
        sb = (mantissa >> 16) & 0xff
        sc = (mantissa >> 8) & 0xff
        sd = mantissa & 0xff

        ibm = IBMFloat.from_bytes((sa, sb, sc, sd))
        assert ibm.is_subnormal()
        normalized = ibm.normalize()
        assert not normalized.is_subnormal()

    @given(integers(128, 255),
           integers(0, 255),
           integers(0, 255),
           integers(4, 23))
    def test_zero_subnormal(self, b, c, d, shift):
        mantissa = (b << 16) | (c << 8) | d
        assume(mantissa != 0)
        mantissa >>= shift
        assert mantissa != 0

        sa = EXPONENT_BIAS
        sb = (mantissa >> 16) & 0xff
        sc = (mantissa >> 8) & 0xff
        sd = mantissa & 0xff

        ibm = IBMFloat.from_bytes((sa, sb, sc, sd))
        assert ibm.is_subnormal()
        z = ibm.zero_subnormal()
        assert z.is_zero()

    @given(integers(0, 255),
           integers(0, 255),
           integers(0, 255),
           integers(0, 255))
    def test_abs(self, a, b, c, d):
        ibm = IBMFloat.from_bytes((a, b, c, d))
        abs_ibm = abs(ibm)
        assert abs_ibm.signbit >= 0

    @given(integers(0, 255),
           integers(0, 255),
           integers(0, 255),
           integers(0, 255))
    def test_negate_non_zero(self, a, b, c, d):
        ibm = IBMFloat.from_bytes((a, b, c, d))
        assume(not ibm.is_zero())
        negated = -ibm
        assert ibm.signbit != negated.signbit

    def test_negate_zero(self):
        zero = IBMFloat.from_float(0.0)
        negated = -zero
        assert negated.is_zero()

    @given(any_ibm_compatible_floats)
    def test_signbit(self, f):
        ltz = f < 0
        ibm = IBMFloat.from_float(f)
        assert ltz == ibm.signbit

    @given(ibm_compatible_floats(-1.0, +1.0),
           integers(-256, 255))
    def test_ldexp_frexp(self, fraction, exponent):
        try:
            ibm = IBMFloat.ldexp(fraction, exponent)
        except (OverflowError, FloatingPointError):
            raise UnsatisfiedAssumption
        else:
            f, e = ibm.frexp()
            assert almost_equal(fraction * 2**exponent, f * 2**e, epsilon=EPSILON_IBM_FLOAT)

    @given(any_ibm_compatible_floats,
           ibm_compatible_floats(0.0, 1.0))
    def test_add(self, f, p):
        a = f * p
        b = f - a

        try:
            ibm_a = IBMFloat.from_float(a)
            ibm_b = IBMFloat.from_float(b)
            ibm_c = ibm_a + ibm_b
        except FloatingPointError:
            raise UnsatisfiedAssumption

        ieee_a = float(ibm_a)
        ieee_b = float(ibm_b)
        ieee_c = ieee_a + ieee_b

        assert almost_equal(ieee_c, ibm_c, epsilon=EPSILON_IBM_FLOAT * 4)

    @given(ibm_compatible_non_negative_floats,
           ibm_compatible_non_negative_floats)
    def test_sub(self, a, b):
        try:
            ibm_a = IBMFloat.from_float(a)
            ibm_b = IBMFloat.from_float(b)
            ibm_c = ibm_a - ibm_b
        except FloatingPointError:
            raise UnsatisfiedAssumption

        ieee_a = float(ibm_a)
        ieee_b = float(ibm_b)
        ieee_c = ieee_a - ieee_b

        assert almost_equal(ieee_c, ibm_c, epsilon=EPSILON_IBM_FLOAT)
