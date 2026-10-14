from __future__ import annotations

# pyqtgraph 0.14.0 Qt contexts; UI text only, never parameter names or values.
PLOT_QT_MESSAGES: tuple[tuple[str, str, str], ...] = (
    (
        'Exporter',
        'Name',
        'plot.qt.exporter.name',
    ),
    (
        'Exporter',
        'Print Document',
        'plot.qt.exporter.print_document',
    ),
    (
        'Exporter',
        'Scalable Vector Graphics',
        'plot.qt.exporter.scalable_vector_graphics',
    ),
    (
        'Exporter',
        'antialias',
        'plot.qt.exporter.antialias',
    ),
    (
        'Exporter',
        'background',
        'plot.qt.exporter.background',
    ),
    (
        'Exporter',
        'columnMode',
        'plot.qt.exporter.columnmode',
    ),
    (
        'Exporter',
        'height',
        'plot.qt.exporter.height',
    ),
    (
        'Exporter',
        'invertValue',
        'plot.qt.exporter.invertvalue',
    ),
    (
        'Exporter',
        'precision',
        'plot.qt.exporter.precision',
    ),
    (
        'Exporter',
        'scaling stroke',
        'plot.qt.exporter.scaling_stroke',
    ),
    (
        'Exporter',
        'separator',
        'plot.qt.exporter.separator',
    ),
    (
        'Exporter',
        'width',
        'plot.qt.exporter.width',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Automatically resize this axis whenever the displayed '
            'data is changed.</p></body></html>'
        ),
        'plot.qt.form.axis_auto_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Enables mouse interaction (panning, scaling) for this '
            'axis.</p></body></html>'
        ),
        'plot.qt.form.axis_mouse_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Inverts the display of this axis. (+y points downward '
            'instead of upward)</p></body></html>'
        ),
        'plot.qt.form.axis_invert_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Links this axis with another view. When linked, both v'
            'iews will display the same data range.</p></body></html>'
        ),
        'plot.qt.form.axis_link_tip',
    ),
    (
        'Form',
        '<html><head/><body><p>Maximum value to display for this axis.</p></body></html>',
        'plot.qt.form.axis_max_tip',
    ),
    (
        'Form',
        '<html><head/><body><p>Minimum value to display for this axis.</p></body></html>',
        'plot.qt.form.axis_min_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Percent of data to be visible when auto-scaling. It ma'
            'y be useful to decrease this value for data with spiky noise.</p></body></ht'
            'ml>'
        ),
        'plot.qt.form.axis_percent_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>Set the range for this axis manually. This disables au'
            'tomatic scaling. </p></body></html>'
        ),
        'plot.qt.form.axis_manual_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>When checked, the axis will automatically pan to cente'
            'r on the current data, but the scale along this axis will not change.</p></b'
            'ody></html>'
        ),
        'plot.qt.form.axis_pan_tip',
    ),
    (
        'Form',
        (
            '<html><head/><body><p>When checked, the axis will only auto-scale to data th'
            'at is visible along the orthogonal axis.</p></body></html>'
        ),
        'plot.qt.form.axis_visible_tip',
    ),
    (
        'Form',
        'Alpha',
        'plot.qt.form.alpha',
    ),
    (
        'Form',
        'Auto',
        'plot.qt.form.auto',
    ),
    (
        'Form',
        'Auto Pan Only',
        'plot.qt.form.auto_pan_only',
    ),
    (
        'Form',
        (
            'Automatically downsample data based on the visible range. This assumes X val'
            'ues are uniformly spaced.'
        ),
        'plot.qt.form.tip_25',
    ),
    (
        'Form',
        'Average',
        'plot.qt.form.average',
    ),
    (
        'Form',
        'Clip to View',
        'plot.qt.form.clip_to_view',
    ),
    (
        'Form',
        'Close',
        'plot.qt.form.close',
    ),
    (
        'Form',
        'Copy',
        'plot.qt.form.copy',
    ),
    (
        'Form',
        (
            'Display averages of the curves displayed in this plot. The parameter list al'
            'lows you to choose parameters to average over (if any are available).'
        ),
        'plot.qt.form.tip_30',
    ),
    (
        'Form',
        'Downsample',
        'plot.qt.form.downsample',
    ),
    (
        'Form',
        (
            'Downsample by drawing a saw wave that follows the min and max of the origina'
            'l data. This method produces the best visual representation of the data but '
            'is slower.'
        ),
        'plot.qt.form.tip_32',
    ),
    (
        'Form',
        (
            'Downsample by taking the first of N samples. This method is fastest and leas'
            't accurate.'
        ),
        'plot.qt.form.tip_33',
    ),
    (
        'Form',
        'Downsample by taking the mean of N samples.',
        'plot.qt.form.downsample_by_taking_the_mean_of_n_samples',
    ),
    (
        'Form',
        'Downsample data before plotting. (plot every Nth sample)',
        'plot.qt.form.downsample_data_before_plotting_plot_every_nth_sample',
    ),
    (
        'Form',
        'Export',
        'plot.qt.form.export',
    ),
    (
        'Form',
        'Export format',
        'plot.qt.form.export_format',
    ),
    (
        'Form',
        'Export options',
        'plot.qt.form.export_options',
    ),
    (
        'Form',
        'Forget hidden traces',
        'plot.qt.form.forget_hidden_traces',
    ),
    (
        'Form',
        (
            'If MaxTraces is checked, remove curves from memory after they are hidden (sa'
            'ves memory, but traces can not be un-hidden).'
        ),
        'plot.qt.form.tip_40',
    ),
    (
        'Form',
        (
            'If multiple curves are displayed in this plot, check "Max Traces" and set th'
            'is value to limit the number of traces that are displayed.'
        ),
        'plot.qt.form.tip_41',
    ),
    (
        'Form',
        (
            'If multiple curves are displayed in this plot, check this box to limit the n'
            'umber of traces that are displayed.'
        ),
        'plot.qt.form.tip_42',
    ),
    (
        'Form',
        'Invert Axis',
        'plot.qt.form.invert_axis',
    ),
    (
        'Form',
        'Item to export:',
        'plot.qt.form.item_to_export',
    ),
    (
        'Form',
        'Link Axis:',
        'plot.qt.form.link_axis',
    ),
    (
        'Form',
        'Log X',
        'plot.qt.form.log_x',
    ),
    (
        'Form',
        'Log Y',
        'plot.qt.form.log_y',
    ),
    (
        'Form',
        'Manual',
        'plot.qt.form.manual',
    ),
    (
        'Form',
        'Max Traces:',
        'plot.qt.form.max_traces',
    ),
    (
        'Form',
        'Mean',
        'plot.qt.form.mean',
    ),
    (
        'Form',
        'Mouse Enabled',
        'plot.qt.form.mouse_enabled',
    ),
    (
        'Form',
        'Opacity',
        'plot.qt.form.opacity',
    ),
    (
        'Form',
        'Peak',
        'plot.qt.form.peak',
    ),
    (
        'Form',
        (
            'Plot only the portion of each curve that is visible. This assumes X values a'
            're uniformly spaced.'
        ),
        'plot.qt.form.tip_54',
    ),
    (
        'Form',
        'Points',
        'plot.qt.form.points',
    ),
    (
        'Form',
        'Power Spectrum (FFT)',
        'plot.qt.form.power_spectrum_fft',
    ),
    (
        'Form',
        'Show X Grid',
        'plot.qt.form.show_x_grid',
    ),
    (
        'Form',
        'Show Y Grid',
        'plot.qt.form.show_y_grid',
    ),
    (
        'Form',
        'Subsample',
        'plot.qt.form.subsample',
    ),
    (
        'Form',
        'Subtract Mean',
        'plot.qt.form.subtract_mean',
    ),
    (
        'Form',
        'Visible Data Only',
        'plot.qt.form.visible_data_only',
    ),
    (
        'Form',
        "Y vs. Y'",
        'plot.qt.form.y_vs_y',
    ),
    (
        'Form',
        'dy/dx',
        'plot.qt.form.dy_dx',
    ),
    (
        'ParameterItem',
        'Remove',
        'plot.qt.parameteritem.remove',
    ),
    (
        'ParameterItem',
        'Rename',
        'plot.qt.parameteritem.rename',
    ),
    (
        'PlotItem',
        'Alpha',
        'plot.qt.plotitem.alpha',
    ),
    (
        'PlotItem',
        'Average',
        'plot.qt.plotitem.average',
    ),
    (
        'PlotItem',
        'Downsample',
        'plot.qt.plotitem.downsample',
    ),
    (
        'PlotItem',
        'Grid',
        'plot.qt.plotitem.grid',
    ),
    (
        'PlotItem',
        'Plot Options',
        'plot.qt.plotitem.plot_options',
    ),
    (
        'PlotItem',
        'Points',
        'plot.qt.plotitem.points',
    ),
    (
        'PlotItem',
        'Transforms',
        'plot.qt.plotitem.transforms',
    ),
    (
        'ViewBox',
        '1 button',
        'plot.qt.viewbox.1_button',
    ),
    (
        'ViewBox',
        '3 button',
        'plot.qt.viewbox.3_button',
    ),
    (
        'ViewBox',
        'Mouse Mode',
        'plot.qt.viewbox.mouse_mode',
    ),
    (
        'ViewBox',
        'View All',
        'plot.qt.viewbox.view_all',
    ),
    (
        'ViewBox',
        'ViewBox options',
        'plot.qt.viewbox.viewbox_options',
    ),
    (
        'ViewBox',
        'axis',
        'plot.qt.viewbox.axis',
    ),
    (
        'Exporter',
        'Image File (PNG, TIF, JPG, ...)',
        'plot.qt.exporter.image_format',
    ),
    (
        'Exporter',
        'CSV of original plot data',
        'plot.qt.exporter.csv_format',
    ),
    (
        'Exporter',
        'Scalable Vector Graphics (SVG)',
        'plot.qt.exporter.svg_format',
    ),
    (
        'Exporter',
        'HDF5 Export: plot (x,y)',
        'plot.qt.exporter.hdf5_format',
    ),
    (
        'Exporter',
        'Matplotlib Window',
        'plot.qt.exporter.matplotlib_format',
    ),
    (
        'Exporter',
        'Printer',
        'plot.qt.exporter.printer_format',
    ),
    (
        'PlotExport',
        'Entire Scene',
        'plot.qt.plotexport.entire_scene',
    ),
    (
        'PlotExport',
        'Plot',
        'plot.qt.plotexport.plot',
    ),
    (
        'PlotExport',
        'ViewBox',
        'plot.qt.plotexport.view_box',
    ),
    (
        'PlotExport',
        'Parameter',
        'plot.qt.plotexport.parameter',
    ),
    (
        'PlotExport',
        'Value',
        'plot.qt.plotexport.value',
    ),
    (
        'PlotExport',
        'comma',
        'plot.qt.plotexport.comma',
    ),
    (
        'PlotExport',
        'tab',
        'plot.qt.plotexport.tab',
    ),
    (
        'PlotExport',
        '(x,y) per plot',
        'plot.qt.plotexport.xy_per_plot',
    ),
    (
        'PlotExport',
        '(x,y,y,y) for all plots',
        'plot.qt.plotexport.shared_x',
    ),
    (
        'PlotExport',
        'False',
        'plot.qt.plotexport.false',
    ),
    (
        'PlotExport',
        'True',
        'plot.qt.plotexport.true',
    ),
    ('GraphicsScene', 'Export...', 'plot.qt.graphicsscene.export'),
)
