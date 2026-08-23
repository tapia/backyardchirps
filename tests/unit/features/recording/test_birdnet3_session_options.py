from backyardchirps.features.recording.audio.birdnet3.analyzer import build_session_options


def test_inference_is_capped_to_the_thread_count_it_is_given() -> None:
    session_options = build_session_options(2)

    assert session_options.intra_op_num_threads == 2
    # One inference at a time. Running operators in parallel on top of the intra-op
    # threads would put the whole machine back to work at once, which is the thing
    # this is here to avoid.
    assert session_options.inter_op_num_threads == 1


def test_a_single_thread_is_allowed() -> None:
    # The setting goes down to 1 on a station where two threads still leave audible
    # noise and there is time budget to spare.
    assert build_session_options(1).intra_op_num_threads == 1


def test_idle_threads_do_not_spin() -> None:
    session_options = build_session_options(2)

    # Spinning is what makes the pool burn every core between operators, which is most
    # of the current step the microphone picks up.
    assert session_options.get_session_config_entry("session.intra_op.allow_spinning") == "0"
