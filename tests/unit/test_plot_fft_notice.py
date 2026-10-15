from __future__ import annotations

import numpy as np
import pytest

from underline_retldc.core.plot_analysis import PlotAnalysis_FFTNotice, PlotAnalysis_Select


@pytest.mark.parametrize("time,notice", [
    ([0., 1., 2.], ""),
    ([0., .9, 2.], "resampled"),
    ([0., .1, 1., 2.], "resampled"),
    ([0., 1., 2., 6.], "resampled_gaps"),
])
def test_native_fft_interpolation_is_disclosed_without_blocking(time, notice) -> None:
    time = np.array(time)
    time.setflags(write=False)
    mask, error = PlotAnalysis_Select(time, np.ones(time.size), active_only=False,
                                      interval=None, fft=True)
    assert error == "" and np.all(mask)
    assert PlotAnalysis_FFTNotice(time) == notice


@pytest.mark.parametrize("time,values,reason", [
    ([], [], "samples"),
    ([1], [1], "samples"),
    ([0, 0, 1], [1, 1, 1], "timestamps"),
    ([1, 0, 2], [1, 1, 1], "timestamps"),
    ([0, np.nan, 2], [1, 1, 1], "timestamps"),
    ([0, 1, 2], [1, np.nan, 1], "gaps"),
    ([0, 1, 2], [1, np.inf, 1], "gaps"),
])
def test_fft_basic_input_protection(time, values, reason) -> None:
    _, notice = PlotAnalysis_Select(np.array(time), np.array(values),
                                    active_only=False, interval=None, fft=True)
    assert notice == reason
