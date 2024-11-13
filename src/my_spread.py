from gspread.utils import ValueInputOption
from gspread_pandas import Spread
from gspread_pandas.exceptions import MissMatchException
from gspread_pandas.util import fillna, parse_df_col_names, get_cell_as_tuple, is_indexes, find_col_indexes, ROW, COL, \
    get_range


class MySpread(Spread):

    def df_to_sheet(
            self,
            df,
            index=True,
            headers=True,
            start=(1, 1),
            replace=False,
            sheet=None,
            raw_columns=None,
            freeze_index=False,
            freeze_headers=False,
            fill_value=None,
            add_filter=False,
            merge_headers=False,
            flatten_headers_sep=None,
            merge_index=False,
    ):
        """
        Save a DataFrame into a worksheet.

        Parameters
        ----------
        df : DataFrame
            the DataFrame to save
        index : bool
            whether to include the index in worksheet (default True)
        headers : bool
            whether to include the headers in the worksheet (default True)
        start : tuple,str
            tuple indicating (row, col) or string like 'A1' for top left
            cell (default (1,1))
        replace : bool
            whether to remove everything in the sheet first (default False)
        sheet : str,int,Worksheet
            optional, if you want to open or create a different sheet
            before saving,
            see :meth:`open_sheet <gspread_pandas.spread.Spread.open_sheet>`
            (default None)
        raw_columns : list, str
            optional, list of columns from your dataframe that you want
            interpreted as RAW input in google sheets. This can be column
            names or column numbers.
        freeze_index : bool
            whether to freeze the index columns (default False)
        freeze_headers : bool
            whether to freeze the header rows (default False)
        fill_value : str
            value to fill nulls with (default '')
        add_filter : bool
            whether to add a filter to the uploaded sheet (default False)
        merge_headers : bool
            whether to merge cells in the header that have the same value
            (default False)
        flatten_headers_sep : str
            if you want to flatten your multi-headers to a single row,
            you can pass the string that you'd like to use to concatenate
            the levels, for example, ': ' (default None)
        merge_index : bool
            whether to merge cells in the index that have the same value
            (default False)

        Returns
        -------
        None
        """
        self._ensure_sheet(sheet)

        include_index = index
        header = df.columns
        index = df.index
        index_size = index.nlevels if include_index else 0
        header_size = header.nlevels

        if include_index:
            df = df.reset_index()

        df_list = df.values.tolist()

        if headers:
            header_rows = parse_df_col_names(
                df, include_index, index_size, flatten_headers_sep
            )
            df_list = header_rows + df_list

        start = get_cell_as_tuple(start)

        sheet_rows, sheet_cols = self.get_sheet_dims()
        req_rows = len(df_list) + (start[ROW] - 1)
        req_cols = len(df_list[0]) + (start[COL] - 1) or 1

        end = (req_rows, req_cols)

        if replace:
            # this takes care of resizing
            self.clear_sheet(req_rows, req_cols)
        else:
            # make sure sheet is large enough
            self.sheet.resize(max(sheet_rows, req_rows), max(sheet_cols, req_cols))

        if raw_columns:
            if is_indexes(raw_columns):
                offset = index_size + start[COL] - 1
                raw_columns = [ix + offset for ix in raw_columns]
            else:
                raw_columns = find_col_indexes(
                    raw_columns, header, start[COL] + index_size
                )

        self.update_cells(
            start=start,
            end=end,
            vals=[str(val) if val is not None else None for row in df_list for val in row],
            raw_columns=raw_columns,
        )

        self.freeze(
            None if not freeze_headers else header_size + start[ROW] - 1,
            None if not freeze_index else index_size + start[COL] - 1,
        )

        if add_filter:
            self.add_filter(
                (header_size + start[ROW] - 2, start[COL] - 1), (req_rows, req_cols)
            )

        if merge_headers:
            self._merge_index(start, header, index_size, "columns")

        if include_index and merge_index:
            self._merge_index(start, index, header_size, "index")

        self.refresh_spread_metadata()

    def update_cells(self, start, end, vals, sheet=None, raw_columns=None):
        """
        Update the values in a given range. The values should be listed in order from
        left to right across rows.

        Parameters
        ----------
        start : tuple,str
            tuple indicating (row, col) or string like 'A1'
        end : tuple,str
            tuple indicating (row, col) or string like 'Z20'
        vals : list
            array of values to populate
        sheet : str,int,Worksheet
            optional, if you want to open a different sheet first,
            see :meth:`open_sheet <gspread_pandas.spread.Spread.open_sheet>`
            (default None)
        raw_columns : list, int
            optional, list of column numbers in the google sheet that should be
            interpreted as "RAW" input

        Returns
        -------
        None
        """
        self._ensure_sheet(sheet)

        for start_cell, end_cell, val_chunks in self._get_update_chunks(
                start, end, vals
        ):
            rng = get_range(start_cell, end_cell)

            cells = self.sheet.range(rng)

            if len(val_chunks) != len(cells):
                raise MissMatchException(
                    "Number of chunked values doesn't match number of cells"
                )

            for val, cell in zip(val_chunks, cells):
                cell.value = val

            if raw_columns:
                assert isinstance(
                    raw_columns, list
                ), "raw_columns must be a list of ints"
                raw_cells = [i for i in cells if i.col in raw_columns]
                self.sheet.update_cells(raw_cells, ValueInputOption.raw)
            else:
                raw_cells = []

            user_cells = [i for i in cells if i not in raw_cells and i.value is not None]
            if user_cells:
                self.sheet.update_cells(user_cells, ValueInputOption.user_entered)
