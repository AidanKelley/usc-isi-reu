In order to recreate the two files, you'll need to first do

``` python -m venv env && source env/bin/activate ```

You'll then have to install the requirements

``` pip install -r requirements.txt ```

You'll additionally have to install the version of SoMEF that I just updated. Do

```pushd .. && git clone https://github.com/aidankelley/somef.git && popd ```

Then, to install SoMEF do

``` pip install -e ../somef/somef\ package ```

To setup SoMEF, do

``` somef configure ```

and follow instructions. Then, you run these commands

``` python main.py ../somef/data/description.csv --csv -o somef_repos_out.ttl ```

``` python main.py repos.txt -o smaller_example.ttl ``` 
